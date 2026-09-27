from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class FutureVarianceTarget(TypedDict):
    security: SecurityIdentity
    sampling_minutes: Literal[5, 10, 15]
    price_basis: Literal["as_printed", "split_adjusted"]
    algorithm_version: str
    origin_session_date: date
    horizon_sessions: Literal[5, 20]
    first_target_session_date: date
    last_target_session_date: date
    average_whole_day_variance: float
    realized_session_count: int
    target_version: Literal["whole_day_variance_v1"]
