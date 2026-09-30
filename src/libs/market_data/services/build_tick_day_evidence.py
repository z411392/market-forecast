import json
from datetime import datetime, timedelta
from hashlib import sha256
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from libs.market_data.dtos.canonical_transaction_tick import (
    CanonicalTransactionTick,
)
from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)
from libs.realized_variance.constants.taiwan_realized_kernel_estimator_version import (
    TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
)


def build_tick_day_evidence(
    *,
    request: HistoricalTickRequestSpec,
    security: SecurityIdentity,
    provider_version: str,
    sdk_observation: bytes,
    transactions: tuple[CanonicalTransactionTick, ...],
) -> tuple[bytes, TickDayEvidenceReceipt]:
    request_sha256 = build_historical_tick_request_sha256(request)

    if (
        not isinstance(provider_version, str)
        or not provider_version
        or provider_version.strip() != provider_version
    ):
        raise InvalidProviderCaptureInputError(
            "tick_day_evidence_invalid_provider_version"
        )
    if type(sdk_observation) is not bytes or not sdk_observation:
        raise InvalidProviderCaptureInputError(
            "tick_day_evidence_invalid_sdk_observation"
        )
    if not transactions:
        raise InvalidProviderCaptureInputError(
            "tick_day_evidence_empty_transactions"
        )

    try:
        timezone_name = security["timezone"]
        security_symbol = security["symbol"]
    except KeyError as error:
        raise InvalidProviderCaptureInputError(
            "tick_day_evidence_invalid_security"
        ) from error

    if request["source_symbol"] != security_symbol:
        raise InvalidProviderCaptureInputError(
            "tick_day_evidence_source_symbol_mismatch"
        )

    try:
        local_timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise InvalidProviderCaptureInputError(
            "tick_day_evidence_invalid_timezone"
        ) from error

    session_date = request["session_date"]
    time_start = request["time_start_local"]
    time_end = request["time_end_local"]
    previous_time: datetime | None = None
    duplicate_timestamp_adjacency_count = 0
    closing_indices: list[int] = []
    serialized_transactions: list[dict[str, object]] = []

    for index, tick in enumerate(transactions):
        if tick["security"] != security:
            raise InvalidProviderCaptureInputError(
                "tick_day_evidence_mixed_security"
            )
        if tick["session_date"] != session_date:
            raise InvalidProviderCaptureInputError(
                "tick_day_evidence_session_mismatch"
            )

        observed_at = tick["observed_at_utc"]
        if (
            not isinstance(observed_at, datetime)
            or observed_at.tzinfo is None
            or observed_at.utcoffset() != timedelta(0)
        ):
            raise InvalidProviderCaptureInputError(
                "tick_day_evidence_timestamp_not_utc"
            )
        if previous_time is not None:
            if observed_at < previous_time:
                raise InvalidProviderCaptureInputError(
                    "tick_day_evidence_timestamps_decreasing"
                )
            if observed_at == previous_time:
                duplicate_timestamp_adjacency_count += 1
        previous_time = observed_at

        local_observed = observed_at.astimezone(local_timezone)
        if local_observed.date() != session_date:
            raise InvalidProviderCaptureInputError(
                "tick_day_evidence_local_session_date_mismatch"
            )
        local_time = local_observed.time()
        if local_time < time_start or local_time > time_end:
            raise InvalidProviderCaptureInputError(
                "tick_day_evidence_timestamp_outside_request"
            )

        price = _positive_finite_number(
            tick["price"],
            "tick_day_evidence_invalid_price",
        )
        volume = _positive_finite_number(
            tick["volume"],
            "tick_day_evidence_invalid_volume",
        )

        if (
            local_time.hour == time_end.hour
            and local_time.minute == time_end.minute
        ):
            closing_indices.append(index)

        serialized_transactions.append(
            {
                "observed_at_utc": observed_at.isoformat(),
                "price": price,
                "volume": volume,
            }
        )

    if not closing_indices:
        raise InvalidProviderCaptureInputError(
            "tick_day_evidence_missing_closing_auction"
        )

    transaction_payload = {
        "security": security,
        "session_date": session_date.isoformat(),
        "source_symbol": request["source_symbol"],
        "transactions": serialized_transactions,
    }
    transaction_sequence = (
        json.dumps(
            transaction_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    first_tick = transactions[0]
    closing_tick = transactions[closing_indices[-1]]
    receipt: TickDayEvidenceReceipt = {
        "provider": "shioaji",
        "provider_version": provider_version,
        "source_symbol": request["source_symbol"],
        "security": security,
        "session_date": session_date,
        "request": request,
        "request_sha256": request_sha256,
        "sdk_observation_sha256": sha256(sdk_observation).hexdigest(),
        "transaction_sequence_sha256": sha256(
            transaction_sequence
        ).hexdigest(),
        "estimator_version": TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
        "tick_count": len(transactions),
        "first_observed_at_utc": first_tick["observed_at_utc"],
        "last_observed_at_utc": transactions[-1]["observed_at_utc"],
        "opening_price": float(first_tick["price"]),
        "closing_auction_observed_at_utc": closing_tick["observed_at_utc"],
        "closing_auction_price": float(closing_tick["price"]),
        "duplicate_timestamp_adjacency_count": (
            duplicate_timestamp_adjacency_count
        ),
    }
    return transaction_sequence, receipt


def _positive_finite_number(value: object, error_code: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise InvalidProviderCaptureInputError(error_code)
    return float(value)
