import math
from collections.abc import Mapping
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


def decode_finmind_stock_kbar(
    payload: Mapping[str, object],
    expected_source_symbol: str,
    security: SecurityIdentity,
) -> tuple[CanonicalMinuteBar, ...]:
    status = payload.get("status")
    if type(status) is not int or status != 200:
        raise InvalidProviderCaptureInputError("finmind_status_not_ok")

    data = payload.get("data")
    if not isinstance(data, list):
        raise InvalidProviderCaptureInputError("finmind_data_missing")
    if not data:
        raise InvalidProviderCaptureInputError("finmind_data_empty")

    try:
        local_timezone = ZoneInfo(security["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise InvalidProviderCaptureInputError("finmind_invalid_timezone") from error

    bars: list[CanonicalMinuteBar] = []
    previous_start_utc: datetime | None = None

    for row in data:
        if not isinstance(row, Mapping):
            raise InvalidProviderCaptureInputError("finmind_row_missing_field")

        required_fields = {
            "date",
            "minute",
            "stock_id",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        if not required_fields.issubset(row):
            raise InvalidProviderCaptureInputError("finmind_row_missing_field")
        if row["stock_id"] != expected_source_symbol:
            raise InvalidProviderCaptureInputError("finmind_stock_id_mismatch")

        local_start = _parse_local_start(
            row["date"],
            row["minute"],
            local_timezone,
        )
        bar_start_utc = local_start.astimezone(timezone.utc)
        if previous_start_utc is not None and bar_start_utc <= previous_start_utc:
            raise InvalidProviderCaptureInputError("finmind_non_increasing_timestamps")

        open_price = _positive_number(row["open"])
        high_price = _positive_number(row["high"])
        low_price = _positive_number(row["low"])
        close_price = _positive_number(row["close"])
        if (
            open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
        ):
            raise InvalidProviderCaptureInputError("finmind_invalid_price")

        volume = _non_negative_number(row["volume"])
        if volume is None:
            raise InvalidProviderCaptureInputError("finmind_invalid_volume")

        if not (low_price <= open_price <= high_price and low_price <= close_price <= high_price):
            raise InvalidProviderCaptureInputError("finmind_invalid_ohlc_envelope")

        bars.append(
            {
                "security": security,
                "bar_start_utc": bar_start_utc,
                "session_date": local_start.date(),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "price_basis": "as_printed",
            }
        )
        previous_start_utc = bar_start_utc

    return tuple(bars)


def _parse_local_start(
    date_value: object,
    minute_value: object,
    local_timezone: ZoneInfo,
) -> datetime:
    if not isinstance(date_value, str) or not isinstance(minute_value, str):
        raise InvalidProviderCaptureInputError("finmind_invalid_local_timestamp")

    raw_value = f"{date_value} {minute_value}"
    try:
        parsed = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise InvalidProviderCaptureInputError("finmind_invalid_local_timestamp") from error

    if parsed.strftime("%Y-%m-%d %H:%M:%S") != raw_value:
        raise InvalidProviderCaptureInputError("finmind_invalid_local_timestamp")
    return parsed.replace(tzinfo=local_timezone)


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
