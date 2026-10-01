from math import fsum, isclose

from libs.realized_variance.domain.services.jitter_log_price_endpoints import (
    jitter_log_price_endpoints,
)
from libs.realized_variance.domain.services.parzen_kernel_weight import (
    parzen_kernel_weight,
)
from libs.realized_variance.domain.services.realized_autocovariance import (
    realized_autocovariance,
)
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def calculate_parzen_realized_kernel(
    log_prices: tuple[float, ...],
    bandwidth: int,
    endpoint_jitter_m: int,
) -> float:
    jittered_prices = jitter_log_price_endpoints(
        log_prices,
        endpoint_jitter_m,
    )
    returns = tuple(
        current - previous
        for previous, current in zip(
            jittered_prices,
            jittered_prices[1:],
        )
    )

    if type(bandwidth) is not int or bandwidth < 1:
        raise InvalidRealizedVarianceInputError(
            "invalid_realized_kernel_bandwidth"
        )

    max_bandwidth = max(1, len(returns) - 1)
    if bandwidth > max_bandwidth:
        raise InvalidRealizedVarianceInputError(
            "realized_kernel_bandwidth_exceeds_available_lags"
        )

    gamma_zero = realized_autocovariance(returns, 0)
    weighted_terms = (
        2.0
        * parzen_kernel_weight(lag / (bandwidth + 1.0))
        * realized_autocovariance(returns, lag)
        for lag in range(1, min(bandwidth, len(returns) - 1) + 1)
    )
    result = fsum((gamma_zero, *weighted_terms))

    if result < 0.0:
        if isclose(result, 0.0, rel_tol=0.0, abs_tol=1e-15):
            return 0.0
        raise InvalidRealizedVarianceInputError(
            "negative_parzen_realized_kernel"
        )

    return result
