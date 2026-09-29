from typing import get_args, get_type_hints

from pytest import mark

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
