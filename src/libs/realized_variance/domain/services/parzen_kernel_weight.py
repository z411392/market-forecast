from math import isfinite

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def parzen_kernel_weight(x: float) -> float:
    if not isfinite(x) or x < 0.0:
        raise InvalidRealizedVarianceInputError("invalid_parzen_kernel_argument")

    if x <= 0.5:
        return 1.0 - 6.0 * x * x + 6.0 * x * x * x
    if x <= 1.0:
        return 2.0 * (1.0 - x) ** 3
    return 0.0
