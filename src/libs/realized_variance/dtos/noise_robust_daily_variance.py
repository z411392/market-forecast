from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class NoiseRobustDailyVariance(TypedDict):
    security: SecurityIdentity
    session_date: date
    price_basis: Literal["as_printed", "split_adjusted"]
    intraday_realized_kernel: float
    overnight_return: float
    overnight_variance: float
    whole_day_variance: float
    tick_count: int
    return_count: int
    bandwidth: int
    noise_variance: float
    sparse_realized_variance: float
    estimator_version: str
