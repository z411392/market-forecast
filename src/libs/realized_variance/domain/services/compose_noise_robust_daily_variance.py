from datetime import date
from math import isfinite
from typing import Literal

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.taiwan_realized_kernel_estimator_version import (
    TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
)
from libs.realized_variance.domain.services.calculate_overnight_log_return import (
    calculate_overnight_log_return,
)
from libs.realized_variance.dtos.noise_robust_daily_variance import (
    NoiseRobustDailyVariance,
)
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def compose_noise_robust_daily_variance(
    *,
    security: SecurityIdentity,
    session_date: date,
    price_basis: Literal["as_printed", "split_adjusted"],
    previous_closing_price: float,
    current_opening_price: float,
    intraday_realized_kernel: float,
    tick_count: int,
    return_count: int,
    bandwidth: int,
    noise_variance: float,
    sparse_realized_variance: float,
) -> NoiseRobustDailyVariance:
    overnight_return = calculate_overnight_log_return(
        previous_closing_price,
        current_opening_price,
    )

    _require_nonnegative_finite(
        intraday_realized_kernel,
        "invalid_intraday_realized_kernel",
    )
    _require_nonnegative_finite(
        noise_variance,
        "invalid_noise_variance",
    )
    _require_nonnegative_finite(
        sparse_realized_variance,
        "invalid_sparse_realized_variance",
    )
    if sparse_realized_variance == 0.0 and noise_variance > 0.0:
        raise InvalidRealizedVarianceInputError("zero_sparse_realized_variance_with_noise")

    if tick_count < 2:
        raise InvalidRealizedVarianceInputError("invalid_tick_count")
    if return_count <= 0 or return_count >= tick_count:
        raise InvalidRealizedVarianceInputError("invalid_return_count")
    if bandwidth <= 0 or bandwidth > max(1, return_count - 1):
        raise InvalidRealizedVarianceInputError("invalid_bandwidth")

    overnight_variance = overnight_return * overnight_return
    whole_day_variance = intraday_realized_kernel + overnight_variance

    return {
        "security": security,
        "session_date": session_date,
        "price_basis": price_basis,
        "intraday_realized_kernel": intraday_realized_kernel,
        "overnight_return": overnight_return,
        "overnight_variance": overnight_variance,
        "whole_day_variance": whole_day_variance,
        "tick_count": tick_count,
        "return_count": return_count,
        "bandwidth": bandwidth,
        "noise_variance": noise_variance,
        "sparse_realized_variance": sparse_realized_variance,
        "estimator_version": TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
    }


def _require_nonnegative_finite(value: float, error_code: str) -> None:
    if not isfinite(value) or value < 0.0:
        raise InvalidRealizedVarianceInputError(error_code)


def _require_positive_finite(value: float, error_code: str) -> None:
    if not isfinite(value) or value <= 0.0:
        raise InvalidRealizedVarianceInputError(error_code)
