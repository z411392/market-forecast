from math import fsum, isfinite

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def estimate_noise_variance_from_subgrids(
    log_prices: tuple[float, ...],
    q: int,
) -> float:
    if len(log_prices) < 2:
        raise InvalidRealizedVarianceInputError("insufficient_prices_for_noise_variance")
    if q <= 0 or q >= len(log_prices):
        raise InvalidRealizedVarianceInputError("invalid_noise_subgrid_stride")
    if any(not isfinite(value) for value in log_prices):
        raise InvalidRealizedVarianceInputError("non_finite_log_price")

    estimates: list[float] = []
    for offset in range(q):
        subgrid = log_prices[offset::q]
        if len(subgrid) < 2:
            continue

        returns = tuple(current - previous for previous, current in zip(subgrid, subgrid[1:]))
        nonzero_returns = tuple(value for value in returns if value != 0.0)
        if not nonzero_returns:
            estimates.append(0.0)
            continue

        realized_variance = fsum(value * value for value in returns)
        estimates.append(realized_variance / (2.0 * len(nonzero_returns)))

    if not estimates:
        raise InvalidRealizedVarianceInputError("no_estimable_noise_subgrid")

    return fsum(estimates) / len(estimates)
