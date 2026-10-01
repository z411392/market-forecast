from math import isfinite

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def realized_autocovariance(
    returns: tuple[float, ...],
    lag: int,
) -> float:
    if not returns:
        raise InvalidRealizedVarianceInputError("empty_realized_returns")
    if lag < 0 or lag >= len(returns):
        raise InvalidRealizedVarianceInputError("invalid_realized_autocovariance_lag")
    if any(not isfinite(value) for value in returns):
        raise InvalidRealizedVarianceInputError("non_finite_realized_return")

    return sum(
        returns[index] * returns[index - lag]
        for index in range(lag, len(returns))
    )
