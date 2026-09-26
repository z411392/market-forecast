from datetime import datetime, timedelta
from typing import Literal

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.realized_variance.dtos.aggregated_intraday_bar import AggregatedIntradayBar
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def aggregate_minute_bars(
    bars: tuple[CanonicalMinuteBar, ...],
    interval_minutes: Literal[5, 10, 15],
    session_start_utc: datetime,
) -> tuple[AggregatedIntradayBar, ...]:
    if interval_minutes not in (5, 10, 15):
        raise InvalidRealizedVarianceInputError("unsupported_interval")
    if not bars:
        raise InvalidRealizedVarianceInputError("empty_bars")
    if not _is_utc_datetime(session_start_utc):
        raise InvalidRealizedVarianceInputError("session_start_not_utc")
    if len(bars) % interval_minutes != 0:
        raise InvalidRealizedVarianceInputError("partial_final_bucket")

    first = bars[0]
    security = first["security"]
    session_date = first["session_date"]
    price_basis = first["price_basis"]

    for index, bar in enumerate(bars):
        if bar["security"] != security:
            raise InvalidRealizedVarianceInputError("mixed_security")
        if bar["session_date"] != session_date:
            raise InvalidRealizedVarianceInputError("mixed_session")
        if bar["price_basis"] != price_basis:
            raise InvalidRealizedVarianceInputError("mixed_price_basis")
        if not _is_utc_datetime(bar["bar_start_utc"]):
            raise InvalidRealizedVarianceInputError("bar_start_not_utc")

        expected_start = session_start_utc + timedelta(minutes=index)
        if bar["bar_start_utc"] != expected_start:
            raise InvalidRealizedVarianceInputError("non_contiguous_minute_bars")

    aggregated: list[AggregatedIntradayBar] = []
    for offset in range(0, len(bars), interval_minutes):
        bucket = bars[offset : offset + interval_minutes]
        aggregated.append(
            {
                "security": security,
                "session_date": session_date,
                "bar_start_utc": bucket[0]["bar_start_utc"],
                "interval_minutes": interval_minutes,
                "open": bucket[0]["open"],
                "high": max(bar["high"] for bar in bucket),
                "low": min(bar["low"] for bar in bucket),
                "close": bucket[-1]["close"],
                "volume": sum(bar["volume"] for bar in bucket),
                "price_basis": price_basis,
                "source_minute_count": len(bucket),
            }
        )

    return tuple(aggregated)


def _is_utc_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)
