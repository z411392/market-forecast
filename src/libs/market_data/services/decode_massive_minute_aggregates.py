import math
from collections.abc import Mapping
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


def decode_massive_minute_aggregates(
    payload: Mapping[str, object],
    expected_source_symbol: str,
    security: SecurityIdentity,
) -> tuple[CanonicalMinuteBar, ...]:
    if payload.get("status") != "OK":
        raise InvalidProviderCaptureInputError("massive_status_not_ok")
    if payload.get("ticker") != expected_source_symbol:
        raise InvalidProviderCaptureInputError("massive_ticker_mismatch")

    adjusted = payload.get("adjusted")
    if type(adjusted) is not bool:
        raise InvalidProviderCaptureInputError("massive_adjusted_not_boolean")

    results = payload.get("results")
    if not isinstance(results, list):
        raise InvalidProviderCaptureInputError("massive_results_missing")
    if not results:
        raise InvalidProviderCaptureInputError("massive_results_empty")

    try:
        local_timezone = ZoneInfo(security["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise InvalidProviderCaptureInputError("massive_invalid_timezone") from error

    price_basis = "split_adjusted" if adjusted else "as_printed"
    bars: list[CanonicalMinuteBar] = []
    previous_timestamp: int | None = None

    for result in results:
        if not isinstance(result, Mapping):
            raise InvalidProviderCaptureInputError("massive_result_missing_field")

        required_fields = {"o", "h", "l", "c", "v", "t"}
        if not required_fields.issubset(result):
            raise InvalidProviderCaptureInputError("massive_result_missing_field")

        open_price = _positive_number(result["o"])
        high_price = _positive_number(result["h"])
        low_price = _positive_number(result["l"])
        close_price = _positive_number(result["c"])
        if open_price is None or high_price is None or low_price is None or close_price is None:
            raise InvalidProviderCaptureInputError("massive_invalid_price")

        volume = _non_negative_number(result["v"])
        if volume is None:
            raise InvalidProviderCaptureInputError("massive_invalid_volume")

        if not (low_price <= open_price <= high_price and low_price <= close_price <= high_price):
            raise InvalidProviderCaptureInputError("massive_invalid_ohlc_envelope")

        raw_timestamp = result["t"]
        if type(raw_timestamp) is not int:
            raise InvalidProviderCaptureInputError("massive_invalid_timestamp")
        if previous_timestamp is not None and raw_timestamp <= previous_timestamp:
            raise InvalidProviderCaptureInputError("massive_non_increasing_timestamps")

        try:
            bar_start_utc = datetime.fromtimestamp(
                raw_timestamp / 1000,
                tz=timezone.utc,
            )
        except (OverflowError, OSError, ValueError) as error:
            raise InvalidProviderCaptureInputError("massive_invalid_timestamp") from error

        bars.append(
            {
                "security": security,
                "bar_start_utc": bar_start_utc,
                "session_date": bar_start_utc.astimezone(local_timezone).date(),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "price_basis": price_basis,
            }
        )
        previous_timestamp = raw_timestamp

    return tuple(bars)


def _positive_number(value: object) -> float | None:
    number = _finite_number(value)
    if number is None or number <= 0.0:
        return None
    return number


def _non_negative_number(value: object) -> float | None:
    number = _finite_number(value)
    if number is None or number < 0.0:
        return None
    return number


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None
