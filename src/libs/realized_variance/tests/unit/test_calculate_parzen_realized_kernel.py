from math import nan

from pytest import approx, mark, raises

from libs.realized_variance.domain.services.calculate_parzen_realized_kernel import (
    calculate_parzen_realized_kernel,
)
from libs.realized_variance.domain.services.calculate_realized_kernel_bandwidth import (
    calculate_realized_kernel_bandwidth,
)
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


@mark.unit
def test_calculate_realized_kernel_bandwidth() -> None:
    assert (
        calculate_realized_kernel_bandwidth(
            noise_variance=1.0,
            sparse_realized_variance=1.0,
            return_count=32,
            bandwidth_constant=3.5134,
        )
        == 29
    )

    assert (
        calculate_realized_kernel_bandwidth(
            noise_variance=0.0,
            sparse_realized_variance=1.0,
            return_count=32,
            bandwidth_constant=3.5134,
        )
        == 1
    )

    assert (
        calculate_realized_kernel_bandwidth(
            noise_variance=1e12,
            sparse_realized_variance=1.0,
            return_count=8,
            bandwidth_constant=3.5134,
        )
        == 7
    )

    with raises(InvalidRealizedVarianceInputError):
        calculate_realized_kernel_bandwidth(
            noise_variance=-1.0,
            sparse_realized_variance=1.0,
            return_count=32,
            bandwidth_constant=3.5134,
        )
    with raises(InvalidRealizedVarianceInputError):
        calculate_realized_kernel_bandwidth(
            noise_variance=1.0,
            sparse_realized_variance=0.0,
            return_count=32,
            bandwidth_constant=3.5134,
        )
    with raises(InvalidRealizedVarianceInputError):
        calculate_realized_kernel_bandwidth(
            noise_variance=1.0,
            sparse_realized_variance=1.0,
            return_count=1,
            bandwidth_constant=3.5134,
        )
    with raises(InvalidRealizedVarianceInputError):
        calculate_realized_kernel_bandwidth(
            noise_variance=nan,
            sparse_realized_variance=1.0,
            return_count=32,
            bandwidth_constant=3.5134,
        )


@mark.unit
def test_calculate_parzen_realized_kernel() -> None:
    result = calculate_parzen_realized_kernel(
        log_prices=(0.0, 2.0, 4.0, 6.0, 8.0, 10.0),
        bandwidth=2,
        endpoint_jitter_m=2,
    )

    assert result == approx(110.0 / 3.0)
    assert result >= 0.0

    assert (
        calculate_parzen_realized_kernel(
            log_prices=(1.0, 1.0, 1.0, 1.0),
            bandwidth=1,
            endpoint_jitter_m=2,
        )
        == approx(0.0)
    )

    with raises(InvalidRealizedVarianceInputError):
        calculate_parzen_realized_kernel(
            log_prices=(0.0, 1.0, 2.0),
            bandwidth=1,
            endpoint_jitter_m=2,
        )
    with raises(InvalidRealizedVarianceInputError):
        calculate_parzen_realized_kernel(
            log_prices=(0.0, 1.0, 2.0, 3.0, 4.0, 5.0),
            bandwidth=3,
            endpoint_jitter_m=2,
        )
    with raises(InvalidRealizedVarianceInputError):
        calculate_parzen_realized_kernel(
            log_prices=(0.0, 1.0, nan, 3.0, 4.0, 5.0),
            bandwidth=1,
            endpoint_jitter_m=2,
        )
