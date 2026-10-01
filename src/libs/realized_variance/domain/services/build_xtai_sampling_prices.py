from datetime import datetime, time, timedelta, timezone
from math import isclose, isfinite
from typing import Literal
from zoneinfo import ZoneInfo

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.closing_auction_observation import ClosingAuctionObservation
from libs.market_data.dtos.session_open_price_observation import SessionOpenPriceObservation
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.dtos.sampled_intraday_price import SampledIntradayPrice
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def build_xtai_sampling_prices(
    bars: tuple[CanonicalMinuteBar, ...],
    session_open: SessionOpenPriceObservation,
    closing_auction: ClosingAuctionObservation,
    interval_minutes: Literal[5, 10, 15],
) -> tuple[SampledIntradayPrice, ...]:
    if interval_minutes not in (5, 10, 15):
        raise InvalidRealizedVarianceInputError("unsupported_interval")
    if not bars:
        raise InvalidRealizedVarianceInputError("empty_xtai_regular_minutes")

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

    previous_start: datetime | None = None
    for bar in bars:
        if bar["security"] != security:
            raise InvalidRealizedVarianceInputError("mixed_security")
        if bar["session_date"] != session_date:
            raise InvalidRealizedVarianceInputError("mixed_session")
        if bar["price_basis"] != price_basis:
            raise InvalidRealizedVarianceInputError("mixed_price_basis")
        if not _is_utc_datetime(bar["bar_start_utc"]):
            raise InvalidRealizedVarianceInputError("bar_start_not_utc")
        if not session_start_utc <= bar["bar_start_utc"] < continuous_end_utc:
            raise InvalidRealizedVarianceInputError("bar_outside_xtai_continuous_session")
        if previous_start is not None and bar["bar_start_utc"] <= previous_start:
            raise InvalidRealizedVarianceInputError("non_increasing_xtai_regular_minutes")
        previous_start = bar["bar_start_utc"]

    if session_open["security"] != security:
        raise InvalidRealizedVarianceInputError("session_open_security_mismatch")
    if session_open["session_date"] != session_date:
        raise InvalidRealizedVarianceInputError("session_open_session_mismatch")
    if session_open["price_basis"] != price_basis:
        raise InvalidRealizedVarianceInputError("session_open_price_basis_mismatch")
    if not _is_utc_datetime(session_open["source_interval_start_utc"]):
        raise InvalidRealizedVarianceInputError("session_open_source_time_not_utc")
    if session_open["source_interval_start_utc"] != first["bar_start_utc"]:
        raise InvalidRealizedVarianceInputError("session_open_source_interval_mismatch")
    if not isfinite(session_open["price"]) or session_open["price"] <= 0.0:
        raise InvalidRealizedVarianceInputError("invalid_session_open_price")
    if not isclose(
        session_open["price"],
        first["open"],
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise InvalidRealizedVarianceInputError("session_open_price_mismatch")

    first_boundary_utc = session_start_utc + timedelta(minutes=interval_minutes)
    if session_open["source_interval_start_utc"] >= first_boundary_utc:
        raise InvalidRealizedVarianceInputError("session_open_outside_first_sampling_bucket")

    if closing_auction["security"] != security:
        raise InvalidRealizedVarianceInputError("closing_auction_security_mismatch")
    if closing_auction["session_date"] != session_date:
        raise InvalidRealizedVarianceInputError("closing_auction_session_mismatch")
    if closing_auction["price_basis"] != price_basis:
        raise InvalidRealizedVarianceInputError("closing_auction_price_basis_mismatch")
    if closing_auction["matched_at_utc"] != closing_at_utc:
        raise InvalidRealizedVarianceInputError("unexpected_xtai_closing_auction_time")

    sampled: list[SampledIntradayPrice] = []
    boundary = first_boundary_utc
    window_start = session_start_utc
    bar_index = 0
    latest_observed_bar: CanonicalMinuteBar | None = None

    while boundary < closing_at_utc:
        if boundary > continuous_end_utc:
            raise InvalidRealizedVarianceInputError(
                "sampling_boundary_inside_closing_auction"
            )

        bucket_observed_bar: CanonicalMinuteBar | None = None
        while bar_index < len(bars) and bars[bar_index]["bar_start_utc"] < boundary:
            current = bars[bar_index]
            latest_observed_bar = current
            if current["bar_start_utc"] >= window_start:
                bucket_observed_bar = current
            bar_index += 1

        source_bar = bucket_observed_bar or latest_observed_bar
        if source_bar is None:
            raise InvalidRealizedVarianceInputError("missing_previous_tick_observation")

        observation_mode: Literal["observed_bucket_close", "previous_tick"]
        if bucket_observed_bar is not None:
            observation_mode = "observed_bucket_close"
        else:
            observation_mode = "previous_tick"

        source_start = source_bar["bar_start_utc"]
        source_end = source_start + timedelta(minutes=1)
        if source_end > boundary:
            raise InvalidRealizedVarianceInputError(
                "sample_source_after_sampling_boundary"
            )
        if observation_mode == "observed_bucket_close" and source_start < window_start:
            raise InvalidRealizedVarianceInputError(
                "observed_source_outside_sampling_bucket"
            )
        if observation_mode == "previous_tick" and source_end > window_start:
            raise InvalidRealizedVarianceInputError(
                "previous_tick_source_inside_sampling_bucket"
            )

        sampled.append(
            {
                "security": security,
                "session_date": session_date,
                "observed_at_utc": boundary,
                "sampling_minutes": interval_minutes,
                "role": "regular_interval_close",
                "price": source_bar["close"],
                "price_basis": price_basis,
                "source_interval_start_utc": source_start,
                "source_interval_end_utc": source_end,
                "observation_mode": observation_mode,
                "staleness_lower_bound_seconds": (
                    boundary - source_end
                ).total_seconds(),
                "staleness_upper_bound_seconds": (
                    boundary - source_start
                ).total_seconds(),
                "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
            }
        )
        window_start = boundary
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
            "source_interval_start_utc": closing_at_utc,
            "source_interval_end_utc": closing_at_utc,
            "observation_mode": "closing_auction",
            "staleness_lower_bound_seconds": 0.0,
            "staleness_upper_bound_seconds": 0.0,
            "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
        }
    )
    return tuple(sampled)


def _is_utc_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)
