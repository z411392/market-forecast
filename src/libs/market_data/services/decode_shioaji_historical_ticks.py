import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from libs.market_data.dtos.canonical_transaction_tick import (
    CanonicalTransactionTick,
)
from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)

_REQUIRED_FIELDS = (
    "ts",
    "close",
    "volume",
    "bid_price",
    "bid_volume",
    "ask_price",
    "ask_volume",
    "tick_type",
)


def decode_shioaji_historical_ticks(
    *,
    payload: Mapping[str, object],
    request: HistoricalTickRequestSpec,
    security: SecurityIdentity,
    provider_version: str,
) -> tuple[bytes, tuple[CanonicalTransactionTick, ...]]:
    build_historical_tick_request_sha256(request)

    if (
        not isinstance(provider_version, str)
        or not provider_version
        or provider_version.strip() != provider_version
    ):
        raise InvalidProviderCaptureInputError(
            "shioaji_tick_decode_invalid_provider_version"
        )
    if request["source_symbol"] != security.get("symbol"):
        raise InvalidProviderCaptureInputError(
            "shioaji_tick_decode_security_symbol_mismatch"
        )

    try:
        local_timezone = ZoneInfo(security["timezone"])
    except (KeyError, ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise InvalidProviderCaptureInputError(
            "shioaji_tick_decode_invalid_timezone"
        ) from error

    normalized: dict[str, list[int | float]] = {}
    for field in _REQUIRED_FIELDS:
        if field not in payload:
            raise InvalidProviderCaptureInputError(
                f"shioaji_tick_decode_missing_field:{field}"
            )
        values = _sequence(payload[field])
        if values is None:
            raise InvalidProviderCaptureInputError(
                f"shioaji_tick_decode_invalid_field:{field}"
            )
        normalized[field] = [
            _number(value, field=field)
            for value in values
        ]

    tick_count = len(normalized["ts"])
    if tick_count == 0:
        raise InvalidProviderCaptureInputError(
            "shioaji_tick_decode_empty_payload"
        )
    if any(
        len(normalized[field]) != tick_count
        for field in _REQUIRED_FIELDS
    ):
        raise InvalidProviderCaptureInputError(
            "shioaji_tick_decode_inconsistent_lengths"
        )

    transactions: list[CanonicalTransactionTick] = []
    for index in range(tick_count):
        raw_timestamp = normalized["ts"][index]
        if type(raw_timestamp) is not int:
            raise InvalidProviderCaptureInputError(
                "shioaji_tick_decode_invalid_timestamp"
            )

        observed_at_utc = _provider_wall_clock_to_utc(
            raw_timestamp,
            local_timezone,
        )
        transactions.append(
            {
                "security": security,
                "session_date": request["session_date"],
                "observed_at_utc": observed_at_utc,
                "price": float(normalized["close"][index]),
                "volume": float(normalized["volume"][index]),
            }
        )

    sdk_payload = {
        "payload": normalized,
        "provider": "shioaji",
        "provider_version": provider_version,
        "request": {
            "query_type": request["query_type"],
            "session_date": request["session_date"].isoformat(),
            "source_symbol": request["source_symbol"],
            "time_end_local": request["time_end_local"].isoformat(),
            "time_start_local": request["time_start_local"].isoformat(),
        },
    }
    sdk_observation = (
        json.dumps(
            sdk_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    return sdk_observation, tuple(transactions)


def _sequence(value: object) -> tuple[object, ...] | None:
    if isinstance(value, (str, bytes, bytearray)):
        return None
    if isinstance(value, Sequence):
        return tuple(value)

    to_list = getattr(value, "tolist", None)
    if callable(to_list):
        converted = to_list()
        if isinstance(converted, list):
            return tuple(converted)
    return None


def _number(value: object, *, field: str) -> int | float:
    item = getattr(value, "item", None)
    if callable(item):
        value = item()

    if isinstance(value, bool):
        raise InvalidProviderCaptureInputError(
            f"shioaji_tick_decode_invalid_number:{field}"
        )
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and isfinite(value):
        return float(value)
    raise InvalidProviderCaptureInputError(
        f"shioaji_tick_decode_invalid_number:{field}"
    )


def _provider_wall_clock_to_utc(
    raw_timestamp: int,
    local_timezone: ZoneInfo,
) -> datetime:
    seconds, nanoseconds = divmod(raw_timestamp, 1_000_000_000)
    if nanoseconds % 1_000 != 0:
        raise InvalidProviderCaptureInputError(
            "shioaji_tick_decode_timestamp_not_microsecond_representable"
        )

    try:
        wall_clock = datetime.fromtimestamp(
            seconds,
            tz=timezone.utc,
        ).replace(
            tzinfo=None,
            microsecond=nanoseconds // 1_000,
        )
    except (OverflowError, OSError, ValueError) as error:
        raise InvalidProviderCaptureInputError(
            "shioaji_tick_decode_invalid_timestamp"
        ) from error

    local_observed = wall_clock.replace(tzinfo=local_timezone)
    return local_observed.astimezone(timezone.utc)
