from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from math import isfinite
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


def decode_alpaca_stock_bars(
    *,
    payload: Mapping[str, object],
    expected_source_symbol: str,
    security: SecurityIdentity,
    price_basis: Literal["as_printed", "split_adjusted"],
) -> tuple[CanonicalMinuteBar, ...]:
    symbol = payload.get("symbol")
    if symbol != expected_source_symbol:
        raise InvalidProviderCaptureInputError(
            "alpaca_symbol_mismatch"
        )
    if price_basis not in ("as_printed", "split_adjusted"):
        raise InvalidProviderCaptureInputError(
            "alpaca_invalid_price_basis"
        )
    if payload.get("next_page_token") is not None:
        raise InvalidProviderCaptureInputError(
            "alpaca_unhandled_pagination"
        )

    raw_bars = payload.get("bars")
    if (
        isinstance(raw_bars, (str, bytes, bytearray))
        or not isinstance(raw_bars, Sequence)
        or not raw_bars
    ):
        raise InvalidProviderCaptureInputError(
            "alpaca_invalid_bars"
        )

    try:
        local_timezone = ZoneInfo(security["timezone"])
    except (KeyError, ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise InvalidProviderCaptureInputError(
            "alpaca_invalid_timezone"
        ) from error

    result: list[CanonicalMinuteBar] = []
    previous_start: datetime | None = None
    for raw_bar in raw_bars:
        if not isinstance(raw_bar, Mapping):
            raise InvalidProviderCaptureInputError(
                "alpaca_invalid_bar"
            )
        bar_start = _timestamp(raw_bar.get("t"))
        if previous_start is not None and bar_start <= previous_start:
            raise InvalidProviderCaptureInputError(
                "alpaca_non_increasing_bars"
            )
        previous_start = bar_start

        opening = _positive(raw_bar.get("o"), "alpaca_invalid_open")
        high = _positive(raw_bar.get("h"), "alpaca_invalid_high")
        low = _positive(raw_bar.get("l"), "alpaca_invalid_low")
        close = _positive(raw_bar.get("c"), "alpaca_invalid_close")
        volume = _nonnegative(
            raw_bar.get("v"),
            "alpaca_invalid_volume",
        )
        if (
            low > high
            or not low <= opening <= high
            or not low <= close <= high
        ):
            raise InvalidProviderCaptureInputError(
                "alpaca_invalid_ohlc_envelope"
            )

        result.append(
            {
                "security": security,
                "bar_start_utc": bar_start,
                "session_date": bar_start.astimezone(
                    local_timezone
                ).date(),
                "open": opening,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "price_basis": price_basis,
            }
        )

    return tuple(result)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise InvalidProviderCaptureInputError(
            "alpaca_invalid_timestamp"
        )
    normalized = (
        value[:-1] + "+00:00"
        if value.endswith("Z")
        else value
    )
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise InvalidProviderCaptureInputError(
            "alpaca_invalid_timestamp"
        ) from error
    if (
        result.tzinfo is None
        or result.utcoffset() != timedelta(0)
    ):
        raise InvalidProviderCaptureInputError(
            "alpaca_timestamp_not_utc"
        )
    return result


def _positive(value: object, error_code: str) -> float:
    result = _number(value, error_code)
    if result <= 0.0:
        raise InvalidProviderCaptureInputError(error_code)
    return result


def _nonnegative(value: object, error_code: str) -> float:
    result = _number(value, error_code)
    if result < 0.0:
        raise InvalidProviderCaptureInputError(error_code)
    return result


def _number(value: object, error_code: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
    ):
        raise InvalidProviderCaptureInputError(error_code)
    return float(value)
