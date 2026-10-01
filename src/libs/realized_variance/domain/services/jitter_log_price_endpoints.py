from math import fsum, isfinite

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def jitter_log_price_endpoints(
    log_prices: tuple[float, ...],
    endpoint_jitter_m: int,
) -> tuple[float, ...]:
    if endpoint_jitter_m != 2:
        raise InvalidRealizedVarianceInputError("unsupported_endpoint_jitter_m")
    if len(log_prices) < 2 * endpoint_jitter_m:
        raise InvalidRealizedVarianceInputError("insufficient_prices_for_endpoint_jitter")
    if any(not isfinite(value) for value in log_prices):
        raise InvalidRealizedVarianceInputError("non_finite_log_price")

    first = fsum(log_prices[:endpoint_jitter_m]) / endpoint_jitter_m
    last = fsum(log_prices[-endpoint_jitter_m:]) / endpoint_jitter_m
    interior = log_prices[endpoint_jitter_m:-endpoint_jitter_m]
    return (first, *interior, last)
