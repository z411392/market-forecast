from datetime import datetime, timedelta
from math import isfinite, log

from libs.realized_variance.dtos.aggregated_intraday_bar import AggregatedIntradayBar
from libs.realized_variance.dtos.intraday_realized_measures import IntradayRealizedMeasures
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def calculate_intraday_realized_measures(
    bars: tuple[AggregatedIntradayBar, ...],
) -> IntradayRealizedMeasures:
    if not bars:
        raise InvalidRealizedVarianceInputError("empty_aggregated_bars")

    first = bars[0]
    security = first["security"]
    session_date = first["session_date"]
    sampling_minutes = first["interval_minutes"]
    price_basis = first["price_basis"]

    if sampling_minutes not in (5, 10, 15):
        raise InvalidRealizedVarianceInputError("unsupported_sampling_interval")

    returns: list[float] = []
    previous_close: float | None = None

    for index, bar in enumerate(bars):
        if bar["security"] != security:
            raise InvalidRealizedVarianceInputError("mixed_security")
        if bar["session_date"] != session_date:
            raise InvalidRealizedVarianceInputError("mixed_session")
        if bar["interval_minutes"] != sampling_minutes:
            raise InvalidRealizedVarianceInputError("mixed_sampling_interval")
        if bar["price_basis"] != price_basis:
            raise InvalidRealizedVarianceInputError("mixed_price_basis")
        if bar["source_minute_count"] != sampling_minutes:
            raise InvalidRealizedVarianceInputError("partial_aggregated_bar")
        if not _is_utc_datetime(bar["bar_start_utc"]):
            raise InvalidRealizedVarianceInputError("bar_start_not_utc")

        if index > 0:
            expected_start = bars[index - 1]["bar_start_utc"] + timedelta(minutes=sampling_minutes)
            if bar["bar_start_utc"] != expected_start:
                raise InvalidRealizedVarianceInputError("non_contiguous_aggregated_bars")

        closing = bar["close"]
        _require_positive_finite(closing)

        if index == 0:
            opening = bar["open"]
            _require_positive_finite(opening)
            interval_return = log(closing / opening)
        else:
            if previous_close is None:
                raise InvalidRealizedVarianceInputError("missing_previous_close")
            _require_positive_finite(previous_close)
            interval_return = log(closing / previous_close)

        returns.append(interval_return)
        previous_close = closing

    squared = tuple(value * value for value in returns)
    realized_variance = sum(squared)
    realized_quarticity = len(returns) / 3.0 * sum(value * value for value in squared)
    positive_semivariance = sum(
        squared_return
        for interval_return, squared_return in zip(returns, squared, strict=True)
        if interval_return >= 0.0
    )
    negative_semivariance = sum(
        squared_return
        for interval_return, squared_return in zip(returns, squared, strict=True)
        if interval_return < 0.0
    )

    return {
        "security": security,
        "session_date": session_date,
        "sampling_minutes": sampling_minutes,
        "price_basis": price_basis,
        "observation_count": len(returns),
        "realized_variance": realized_variance,
        "realized_quarticity": realized_quarticity,
        "positive_semivariance": positive_semivariance,
        "negative_semivariance": negative_semivariance,
    }


def _is_utc_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _require_positive_finite(value: float | None) -> None:
    if value is None or not isfinite(value) or value <= 0.0:
        raise InvalidRealizedVarianceInputError("non_positive_or_non_finite_price")
