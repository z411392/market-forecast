from datetime import datetime, timedelta
from math import floor, isfinite

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def select_noise_subgrid_stride(
    timestamps: tuple[datetime, ...],
    target_spacing_seconds: int,
) -> int:
    if len(timestamps) < 2:
        raise InvalidRealizedVarianceInputError("insufficient_noise_stride_timestamps")
    if target_spacing_seconds <= 0:
        raise InvalidRealizedVarianceInputError("invalid_noise_target_spacing")

    for value in timestamps:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise InvalidRealizedVarianceInputError("noise_stride_timestamp_not_utc")

    gaps = tuple(
        (current - previous).total_seconds() for previous, current in zip(timestamps, timestamps[1:])
    )
    if any(not isfinite(gap) or gap < 0.0 for gap in gaps):
        raise InvalidRealizedVarianceInputError("decreasing_noise_stride_timestamps")

    elapsed_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
    if not isfinite(elapsed_seconds) or elapsed_seconds <= 0.0:
        raise InvalidRealizedVarianceInputError("zero_elapsed_noise_stride_timestamps")

    average_gap_seconds = elapsed_seconds / (len(timestamps) - 1)
    raw_stride = target_spacing_seconds / average_gap_seconds
    half_up_stride = floor(raw_stride + 0.5)
    return max(1, min(half_up_stride, len(timestamps) - 1))
