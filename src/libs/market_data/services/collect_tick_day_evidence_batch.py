from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.dtos.tick_batch_collection_summary import (
    TickBatchCollectionSummary,
)
from libs.market_data.dtos.tick_day_collection_item import TickDayCollectionItem
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
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
from libs.market_data.services.acquire_and_persist_tick_day_evidence import (
    acquire_and_persist_tick_day_evidence,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)

_MAX_UNCACHED_ACQUISITIONS = 100
_MIN_REMAINING_BYTES = 100 * 1024 * 1024
_MAX_CURRENT_RUN_DELTA_BYTES = 250 * 1024 * 1024


def collect_tick_day_evidence_batch(
    *,
    items: tuple[TickDayCollectionItem, ...],
    fetch_payload: FetchHistoricalTickPayloadPort,
    read_usage: ReadProviderTrafficUsagePort,
    evidence_store: TickDayEvidenceStorePort,
    provider_version: str,
) -> TickBatchCollectionSummary:
    request_hashes = _validate_plan(items, provider_version)

    receipts: list[TickDayEvidenceReceipt] = []
    cache_hit_count = 0
    acquired_count = 0
    deferred_count = 0
    stop_reason: str | None = None
    initial_usage: ProviderTrafficUsage | None = None
    final_usage: ProviderTrafficUsage | None = None
    baseline_used_bytes: int | None = None
    last_used_bytes: int | None = None
    current_run_delta_bytes = 0

    for item, request_sha256 in zip(items, request_hashes, strict=True):
        request = item["request"]

        if evidence_store.contains(request_sha256):
            receipt = acquire_and_persist_tick_day_evidence(
                fetch_payload=fetch_payload,
                read_usage=read_usage,
                evidence_store=evidence_store,
                request=request,
                security=item["security"],
                provider_version=provider_version,
            )
            receipts.append(receipt)
            cache_hit_count += 1
            continue

        if stop_reason is not None:
            deferred_count += 1
            continue

        if acquired_count >= _MAX_UNCACHED_ACQUISITIONS:
            stop_reason = "max_uncached_reached"
            deferred_count += 1
            continue

        usage_before = read_usage()
        _validate_usage(usage_before)
        last_used_bytes = _require_nondecreasing_usage(
            usage_before,
            last_used_bytes,
        )
        if initial_usage is None:
            initial_usage = usage_before
            baseline_used_bytes = usage_before["used_bytes"]
        final_usage = usage_before
        if baseline_used_bytes is None:
            raise ProviderTransportError(
                "tick_batch_collection_missing_usage_baseline"
            )
        current_run_delta_bytes = (
            usage_before["used_bytes"] - baseline_used_bytes
        )

        if usage_before["remaining_bytes"] < _MIN_REMAINING_BYTES:
            stop_reason = "remaining_traffic_guard"
            deferred_count += 1
            continue
        if current_run_delta_bytes >= _MAX_CURRENT_RUN_DELTA_BYTES:
            stop_reason = "current_run_traffic_guard"
            deferred_count += 1
            continue

        try:
            receipt = acquire_and_persist_tick_day_evidence(
                fetch_payload=fetch_payload,
                read_usage=read_usage,
                evidence_store=evidence_store,
                request=request,
                security=item["security"],
                provider_version=provider_version,
            )
        except ProviderTransportError as error:
            if str(error) == "tick_day_acquisition_remaining_traffic_below_guard":
                stop_reason = "remaining_traffic_guard"
                deferred_count += 1
                continue
            raise

        receipts.append(receipt)
        acquired_count += 1

        usage_after = read_usage()
        _validate_usage(usage_after)
        last_used_bytes = _require_nondecreasing_usage(
            usage_after,
            last_used_bytes,
        )
        final_usage = usage_after
        current_run_delta_bytes = usage_after["used_bytes"] - baseline_used_bytes

        if current_run_delta_bytes >= _MAX_CURRENT_RUN_DELTA_BYTES:
            stop_reason = "current_run_traffic_guard"
        elif usage_after["remaining_bytes"] < _MIN_REMAINING_BYTES:
            stop_reason = "remaining_traffic_guard"

    final_reason = stop_reason or "completed"
    return {
        "requested_count": len(items),
        "cache_hit_count": cache_hit_count,
        "acquired_count": acquired_count,
        "deferred_count": deferred_count,
        "receipts": tuple(receipts),
        "initial_usage": initial_usage,
        "final_usage": final_usage,
        "current_run_delta_bytes": current_run_delta_bytes,
        "stop_reason": final_reason,  # type: ignore[typeddict-item]
    }


def _validate_plan(
    items: tuple[TickDayCollectionItem, ...],
    provider_version: str,
) -> tuple[str, ...]:
    if not items:
        raise InvalidProviderCaptureInputError(
            "tick_batch_collection_empty_plan"
        )
    if not isinstance(provider_version, str) or not provider_version:
        raise InvalidProviderCaptureInputError(
            "tick_batch_collection_invalid_provider_version"
        )

    request_hashes: list[str] = []
    seen: set[str] = set()
    for item in items:
        request = item["request"]
        security = item["security"]
        if request["source_symbol"] != security["symbol"]:
            raise InvalidProviderCaptureInputError(
                "tick_batch_collection_security_mismatch"
            )
        request_sha256 = build_historical_tick_request_sha256(request)
        if request_sha256 in seen:
            raise InvalidProviderCaptureInputError(
                "tick_batch_collection_duplicate_request"
            )
        seen.add(request_sha256)
        request_hashes.append(request_sha256)
    return tuple(request_hashes)


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
            "tick_batch_collection_invalid_provider_usage"
        )


def _require_nondecreasing_usage(
    usage: ProviderTrafficUsage,
    previous_used_bytes: int | None,
) -> int:
    used = usage["used_bytes"]
    if previous_used_bytes is not None and used < previous_used_bytes:
        raise ProviderTransportError(
            "tick_batch_collection_provider_usage_decreased"
        )
    return used
