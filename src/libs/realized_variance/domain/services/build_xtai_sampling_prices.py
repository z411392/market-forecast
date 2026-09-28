from datetime import datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.closing_auction_observation import ClosingAuctionObservation
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.dtos.sampled_intraday_price import SampledIntradayPrice
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def build_xtai_sampling_prices(
    bars: tuple[CanonicalMinuteBar, ...],
    closing_auction: ClosingAuctionObservation,
    interval_minutes: Literal[5, 10, 15],
) -> tuple[SampledIntradayPrice, ...]:
    if interval_minutes not in (5, 10, 15):
        raise InvalidRealizedVarianceInputError("unsupported_interval")
    if len(bars) != 265:
        raise InvalidRealizedVarianceInputError("unexpected_xtai_regular_minute_count")

    first = bars[0]
    security = first["security"]
    session_date = first["session_date"]
    price_basis = first["price_basis"]

    if (
        security["exchange"] != "XTAI"
        or security["calendar_id"] != "XTAI"
        or security["timezone"] != "Asia/Taipei"
    ):
        raise InvalidRealizedVarianceInputError("unsupported_xtai_security_identity")

    local_timezone = ZoneInfo("Asia/Taipei")
    session_start_local = datetime.combine(session_date, time(9, 0), tzinfo=local_timezone)
    continuous_end_local = datetime.combine(session_date, time(13, 25), tzinfo=local_timezone)
    closing_at_local = datetime.combine(session_date, time(13, 30), tzinfo=local_timezone)
    session_start_utc = session_start_local.astimezone(timezone.utc)
    continuous_end_utc = continuous_end_local.astimezone(timezone.utc)
    closing_at_utc = closing_at_local.astimezone(timezone.utc)

    for index, bar in enumerate(bars):
        if bar["security"] != security:
            raise InvalidRealizedVarianceInputError("mixed_security")
        if bar["session_date"] != session_date:
            raise InvalidRealizedVarianceInputError("mixed_session")
        if bar["price_basis"] != price_basis:
            raise InvalidRealizedVarianceInputError("mixed_price_basis")
        if not _is_utc_datetime(bar["bar_start_utc"]):
            raise InvalidRealizedVarianceInputError("bar_start_not_utc")
        if bar["bar_start_utc"] != session_start_utc + timedelta(minutes=index):
            raise InvalidRealizedVarianceInputError("non_contiguous_xtai_regular_minutes")

    if bars[-1]["bar_start_utc"] + timedelta(minutes=1) != continuous_end_utc:
        raise InvalidRealizedVarianceInputError("unexpected_xtai_continuous_session_end")
    if closing_auction["security"] != security:
        raise InvalidRealizedVarianceInputError("closing_auction_security_mismatch")
    if closing_auction["session_date"] != session_date:
        raise InvalidRealizedVarianceInputError("closing_auction_session_mismatch")
    if closing_auction["price_basis"] != price_basis:
        raise InvalidRealizedVarianceInputError("closing_auction_price_basis_mismatch")
    if closing_auction["matched_at_utc"] != closing_at_utc:
        raise InvalidRealizedVarianceInputError("unexpected_xtai_closing_auction_time")

    sampled: list[SampledIntradayPrice] = [
        {
            "security": security,
            "session_date": session_date,
            "observed_at_utc": session_start_utc,
            "sampling_minutes": interval_minutes,
            "role": "session_open",
            "price": first["open"],
            "price_basis": price_basis,
            "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
        }
    ]

    boundary = session_start_utc + timedelta(minutes=interval_minutes)
    while boundary < closing_at_utc:
        if boundary > continuous_end_utc:
            raise InvalidRealizedVarianceInputError(
                "sampling_boundary_inside_closing_auction"
            )
        bar_index = int((boundary - session_start_utc).total_seconds() // 60) - 1
        sampled.append(
            {
                "security": security,
                "session_date": session_date,
                "observed_at_utc": boundary,
                "sampling_minutes": interval_minutes,
                "role": "regular_interval_close",
                "price": bars[bar_index]["close"],
                "price_basis": price_basis,
                "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
            }
        )
        boundary += timedelta(minutes=interval_minutes)

    if boundary != closing_at_utc:
        raise InvalidRealizedVarianceInputError("closing_auction_off_sampling_grid")

    sampled.append(
        {
            "security": security,
            "session_date": session_date,
            "observed_at_utc": closing_at_utc,
            "sampling_minutes": interval_minutes,
            "role": "closing_auction_close",
            "price": closing_auction["price"],
            "price_basis": price_basis,
            "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
        }
    )
    return tuple(sampled)


def _is_utc_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)
