from bisect import bisect_right
from datetime import datetime, timedelta
from math import fsum, isfinite

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def estimate_sparse_realized_variance(
    timestamps: tuple[datetime, ...],
    log_prices: tuple[float, ...],
    interval_seconds: int,
    phase_shift_seconds: int,
) -> float:
    if len(timestamps) != len(log_prices) or len(timestamps) < 2:
        raise InvalidRealizedVarianceInputError("invalid_sparse_rv_observation_count")
    if interval_seconds <= 0:
        raise InvalidRealizedVarianceInputError("invalid_sparse_rv_interval")
    if phase_shift_seconds <= 0 or phase_shift_seconds > interval_seconds:
        raise InvalidRealizedVarianceInputError("invalid_sparse_rv_phase_shift")
    if any(not isfinite(value) for value in log_prices):
        raise InvalidRealizedVarianceInputError("non_finite_sparse_rv_log_price")

    for timestamp in timestamps:
        if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
            raise InvalidRealizedVarianceInputError("sparse_rv_timestamp_not_utc")

    gaps = tuple(
        (current - previous).total_seconds()
        for previous, current in zip(timestamps, timestamps[1:])
    )
    if any(not isfinite(gap) or gap <= 0.0 for gap in gaps):
        raise InvalidRealizedVarianceInputError("non_increasing_sparse_rv_timestamps")

    start = timestamps[0]
    end = timestamps[-1]
    phase_estimates: list[float] = []

    for offset_seconds in range(0, interval_seconds, phase_shift_seconds):
        grid_time = start + timedelta(seconds=offset_seconds)
        synchronized_prices: list[float] = []

        while grid_time <= end:
            previous_tick_index = bisect_right(timestamps, grid_time) - 1
            if previous_tick_index >= 0:
                synchronized_prices.append(log_prices[previous_tick_index])
            grid_time += timedelta(seconds=interval_seconds)

        if len(synchronized_prices) < 2:
            continue

        returns = tuple(
            current - previous
            for previous, current in zip(
                synchronized_prices,
                synchronized_prices[1:],
            )
        )
        phase_estimates.append(fsum(value * value for value in returns))

    if not phase_estimates:
        raise InvalidRealizedVarianceInputError("no_estimable_sparse_rv_phase")

    return fsum(phase_estimates) / len(phase_estimates)
