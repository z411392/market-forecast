from libs.realized_variance.constants.taiwan_realized_kernel_estimator_version import (
    TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
)
from libs.realized_variance.dtos.realized_kernel_parameters import RealizedKernelParameters


def build_default_realized_kernel_parameters() -> RealizedKernelParameters:
    return {
        "estimator_version": TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
        "kernel": "parzen",
        "endpoint_jitter_m": 2,
        "bandwidth_constant": 3.5134,
        "sparse_interval_seconds": 1200,
        "sparse_phase_shift_seconds": 1,
        "noise_target_spacing_seconds": 120,
    }
