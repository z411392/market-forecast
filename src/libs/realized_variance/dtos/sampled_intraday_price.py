from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class SampledIntradayPrice(TypedDict):
    security: SecurityIdentity
    session_date: date
    observed_at_utc: datetime
    sampling_minutes: Literal[5, 10, 15]
    role: Literal[
        "regular_interval_close",
        "closing_auction_close",
    ]
    price: float
    price_basis: Literal["as_printed", "split_adjusted"]
    source_interval_start_utc: datetime
    source_interval_end_utc: datetime
    observation_mode: Literal[
        "observed_bucket_close",
        "previous_tick",
        "closing_auction",
    ]
    staleness_lower_bound_seconds: float
    staleness_upper_bound_seconds: float
    algorithm_version: str
