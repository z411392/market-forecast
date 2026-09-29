from math import ceil, isfinite, sqrt

from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def calculate_realized_kernel_bandwidth(
    noise_variance: float,
    sparse_realized_variance: float,
    return_count: int,
    bandwidth_constant: float,
) -> int:
    if not isfinite(noise_variance) or noise_variance < 0.0:
        raise InvalidRealizedVarianceInputError("invalid_realized_kernel_noise_variance")
    if not isfinite(sparse_realized_variance) or sparse_realized_variance <= 0.0:
        raise InvalidRealizedVarianceInputError("invalid_sparse_realized_variance")
    if return_count < 2:
        raise InvalidRealizedVarianceInputError("insufficient_realized_kernel_returns")
    if not isfinite(bandwidth_constant) or bandwidth_constant <= 0.0:
        raise InvalidRealizedVarianceInputError("invalid_realized_kernel_bandwidth_constant")

    if noise_variance == 0.0:
        return 1

    xi_hat = sqrt(noise_variance / sparse_realized_variance)
    raw_bandwidth = (
        bandwidth_constant
        * xi_hat ** (4.0 / 5.0)
        * return_count ** (3.0 / 5.0)
    )
    if not isfinite(raw_bandwidth):
        return return_count - 1

    return max(1, min(ceil(raw_bandwidth), return_count - 1))
