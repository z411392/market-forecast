from math import isfinite, log

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def calculate_overnight_log_return(
    previous_regular_close: float,
    current_regular_open: float,
) -> float:
    if not isfinite(previous_regular_close) or previous_regular_close <= 0.0:
        raise InvalidRealizedVarianceInputError("invalid_previous_regular_close")
    if not isfinite(current_regular_open) or current_regular_open <= 0.0:
        raise InvalidRealizedVarianceInputError("invalid_current_regular_open")

    return log(current_regular_open / previous_regular_close)
