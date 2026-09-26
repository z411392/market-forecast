from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class DailyRealizedMeasures(TypedDict):
    security: SecurityIdentity
    session_date: date
    sampling_minutes: Literal[5, 10, 15]
    price_basis: Literal["as_printed", "split_adjusted"]
    regular_session_variance: float
    overnight_log_return: float
    overnight_variance: float
    whole_day_variance: float
    regular_positive_semivariance: float
    regular_negative_semivariance: float
    whole_day_positive_semivariance: float
    whole_day_negative_semivariance: float
    realized_quarticity: float
    observation_count: int
