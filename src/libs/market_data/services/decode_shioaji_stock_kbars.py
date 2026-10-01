import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.closing_auction_observation import ClosingAuctionObservation
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.session_open_price_observation import SessionOpenPriceObservation
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


def decode_shioaji_stock_kbars(
    payload: Mapping[str, object],
    security: SecurityIdentity,
    expected_session_date: date,
    price_basis: Literal["as_printed", "split_adjusted"],
) -> tuple[
    tuple[CanonicalMinuteBar, ...],
    SessionOpenPriceObservation,
    ClosingAuctionObservation,
]:
    timestamps = _sequence(payload.get("ts"))
    opens = _sequence(payload.get("Open"))
    highs = _sequence(payload.get("High"))
    lows = _sequence(payload.get("Low"))
    closes = _sequence(payload.get("Close"))
    volumes = _sequence(payload.get("Volume"))
    if (
        timestamps is None
        or opens is None
        or highs is None
        or lows is None
        or closes is None
        or volumes is None
    ):
        raise InvalidProviderCaptureInputError("shioaji_kbars_missing_field")

    count = len(timestamps)
    if count == 0 or any(len(values) != count for values in (opens, highs, lows, closes, volumes)):
        raise InvalidProviderCaptureInputError("shioaji_kbars_inconsistent_lengths")

    try:
        local_timezone = ZoneInfo(security["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise InvalidProviderCaptureInputError("shioaji_invalid_timezone") from error

    bars: list[CanonicalMinuteBar] = []
    session_open: SessionOpenPriceObservation | None = None
    closing_auction: ClosingAuctionObservation | None = None
    previous_label: datetime | None = None

    for index in range(count):
        local_label = _local_label(timestamps[index], local_timezone)
        if local_label.date() != expected_session_date:
            raise InvalidProviderCaptureInputError("shioaji_session_date_mismatch")
        if previous_label is not None and local_label <= previous_label:
            raise InvalidProviderCaptureInputError("shioaji_non_increasing_timestamps")

        open_price = _positive_number(opens[index])
        high_price = _positive_number(highs[index])
        low_price = _positive_number(lows[index])
        close_price = _positive_number(closes[index])
        volume = _non_negative_number(volumes[index])
        if open_price is None or high_price is None or low_price is None or close_price is None:
            raise InvalidProviderCaptureInputError("shioaji_invalid_price")
        if volume is None:
            raise InvalidProviderCaptureInputError("shioaji_invalid_volume")
        if not (low_price <= open_price <= high_price and low_price <= close_price <= high_price):
            raise InvalidProviderCaptureInputError("shioaji_invalid_ohlc_envelope")

        label_time = local_label.time()
        if label_time == time(13, 30):
            if index != count - 1 or closing_auction is not None:
                raise InvalidProviderCaptureInputError("shioaji_invalid_closing_auction_position")
            closing_auction = {
                "security": security,
                "session_date": expected_session_date,
                "matched_at_utc": local_label.astimezone(timezone.utc),
                "price": close_price,
                "volume": volume,
                "price_basis": price_basis,
            }
        else:
            if label_time < time(9, 1) or label_time > time(13, 25):
                raise InvalidProviderCaptureInputError("shioaji_unexpected_regular_label")
            bar_start_local = local_label - timedelta(minutes=1)
            bar_start_utc = bar_start_local.astimezone(timezone.utc)
            bar: CanonicalMinuteBar = {
                "security": security,
                "bar_start_utc": bar_start_utc,
                "session_date": expected_session_date,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "price_basis": price_basis,
            }
            if session_open is None:
                session_open = {
                    "security": security,
                    "session_date": expected_session_date,
                    "source_interval_start_utc": bar_start_utc,
                    "price": open_price,
                    "price_basis": price_basis,
                }
            bars.append(bar)

        previous_label = local_label

    if session_open is None:
        raise InvalidProviderCaptureInputError("shioaji_session_open_missing")
    if closing_auction is None:
        raise InvalidProviderCaptureInputError("shioaji_closing_auction_missing")

    return tuple(bars), session_open, closing_auction


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


def _local_label(value: object, local_timezone: ZoneInfo) -> datetime:
    if type(value) is not int:
        raise InvalidProviderCaptureInputError("shioaji_invalid_timestamp")
    seconds, nanoseconds = divmod(value, 1_000_000_000)
    if nanoseconds != 0:
        raise InvalidProviderCaptureInputError("shioaji_invalid_timestamp")

    try:
        wall_clock = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError) as error:
        raise InvalidProviderCaptureInputError("shioaji_invalid_timestamp") from error

    if wall_clock.second != 0 or wall_clock.microsecond != 0:
        raise InvalidProviderCaptureInputError("shioaji_invalid_timestamp")
    return wall_clock.replace(tzinfo=local_timezone)


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
