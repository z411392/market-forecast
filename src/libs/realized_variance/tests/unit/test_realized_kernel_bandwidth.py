from math import nan

from pytest import mark, raises

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
            noise_variance=0.0,
            sparse_realized_variance=0.0,
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


@mark.unit
def test_calculate_realized_kernel_bandwidth_rejects_invalid_inputs() -> None:
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
