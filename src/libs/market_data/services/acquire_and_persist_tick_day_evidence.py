from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt
from libs.market_data.exceptions.provider_capture_evidence_integrity_error import (
    ProviderCaptureEvidenceIntegrityError,
)
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError
from libs.market_data.ports.fetch_historical_tick_payload_port import (
    FetchHistoricalTickPayloadPort,
)
from libs.market_data.ports.read_provider_traffic_usage_port import (
    ReadProviderTrafficUsagePort,
)
from libs.market_data.ports.tick_day_evidence_store_port import (
    TickDayEvidenceStorePort,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)
from libs.market_data.services.build_tick_day_evidence import (
    build_tick_day_evidence,
)
from libs.market_data.services.decode_shioaji_historical_ticks import (
    decode_shioaji_historical_ticks,
)

_MIN_REMAINING_BYTES = 250 * 1024 * 1024


def acquire_and_persist_tick_day_evidence(
    *,
    fetch_payload: FetchHistoricalTickPayloadPort,
    read_usage: ReadProviderTrafficUsagePort,
    evidence_store: TickDayEvidenceStorePort,
    request: HistoricalTickRequestSpec,
    security: SecurityIdentity,
    provider_version: str,
) -> TickDayEvidenceReceipt:
    request_sha256 = build_historical_tick_request_sha256(request)

    if evidence_store.contains(request_sha256):
        receipt = evidence_store.load_receipt(request_sha256)
        if receipt is None:
            raise ProviderCaptureEvidenceIntegrityError(
                "tick_day_acquisition_cached_receipt_missing"
            )
        if receipt["request_sha256"] != request_sha256:
            raise ProviderCaptureEvidenceIntegrityError(
                "tick_day_acquisition_cached_request_hash_mismatch"
            )
        return receipt

    usage = read_usage()
    _validate_usage(usage)
    if usage["remaining_bytes"] < _MIN_REMAINING_BYTES:
        raise ProviderTransportError(
            "tick_day_acquisition_remaining_traffic_below_guard"
        )

    payload = fetch_payload(request)
    sdk_observation, transactions = decode_shioaji_historical_ticks(
        payload=payload,
        request=request,
        security=security,
        provider_version=provider_version,
    )
    transaction_sequence, receipt = build_tick_day_evidence(
        request=request,
        security=security,
        provider_version=provider_version,
        sdk_observation=sdk_observation,
        transactions=transactions,
    )
    evidence_store(
        sdk_observation,
        transaction_sequence,
        receipt,
    )
    return receipt


def _validate_usage(usage: ProviderTrafficUsage) -> None:
    used = usage["used_bytes"]
    limit = usage["limit_bytes"]
    remaining = usage["remaining_bytes"]

    if (
        type(used) is not int
        or type(limit) is not int
        or type(remaining) is not int
        or used < 0
        or limit <= 0
        or remaining < 0
        or used > limit
        or remaining > limit
    ):
        raise ProviderTransportError(
            "tick_day_acquisition_invalid_provider_usage"
        )
