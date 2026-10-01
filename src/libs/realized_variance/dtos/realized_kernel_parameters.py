from typing import Literal, TypedDict


class RealizedKernelParameters(TypedDict):
    estimator_version: str
    kernel: Literal["parzen"]
    endpoint_jitter_m: int
    bandwidth_constant: float
    sparse_interval_seconds: int
    sparse_phase_shift_seconds: int
    noise_target_spacing_seconds: int
