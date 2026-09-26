from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class IntradayRealizedMeasures(TypedDict):
    security: SecurityIdentity
    session_date: date
    sampling_minutes: Literal[5, 10, 15]
    price_basis: Literal["as_printed", "split_adjusted"]
    observation_count: int
    realized_variance: float
    realized_quarticity: float
    positive_semivariance: float
    negative_semivariance: float
