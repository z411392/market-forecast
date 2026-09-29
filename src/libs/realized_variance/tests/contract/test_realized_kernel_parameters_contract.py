from typing import get_args, get_type_hints

from pytest import mark

from libs.realized_variance.constants.taiwan_realized_kernel_estimator_version import (
    TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
)
from libs.realized_variance.domain.services.build_default_realized_kernel_parameters import (
    build_default_realized_kernel_parameters,
)
from libs.realized_variance.dtos.realized_kernel_parameters import RealizedKernelParameters


@mark.contract
def test_realized_kernel_parameters_contract() -> None:
    assert RealizedKernelParameters.__required_keys__ == frozenset(
        {
            "estimator_version",
            "kernel",
            "endpoint_jitter_m",
            "bandwidth_constant",
            "sparse_interval_seconds",
            "sparse_phase_shift_seconds",
            "noise_target_spacing_seconds",
        }
    )

    hints = get_type_hints(RealizedKernelParameters)
    assert hints["estimator_version"] is str
    assert get_args(hints["kernel"]) == ("parzen",)
    assert hints["endpoint_jitter_m"] is int
    assert hints["bandwidth_constant"] is float
    assert hints["sparse_interval_seconds"] is int
    assert hints["sparse_phase_shift_seconds"] is int
    assert hints["noise_target_spacing_seconds"] is int

    assert TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION == "tw-rk-parzen-trades-v1"

    assert build_default_realized_kernel_parameters() == {
        "estimator_version": "tw-rk-parzen-trades-v1",
        "kernel": "parzen",
        "endpoint_jitter_m": 2,
        "bandwidth_constant": 3.5134,
        "sparse_interval_seconds": 1200,
        "sparse_phase_shift_seconds": 1,
        "noise_target_spacing_seconds": 120,
    }
