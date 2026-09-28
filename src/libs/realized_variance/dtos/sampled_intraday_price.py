from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class SampledIntradayPrice(TypedDict):
    security: SecurityIdentity
    session_date: date
    observed_at_utc: datetime
    sampling_minutes: Literal[5, 10, 15]
    role: Literal[
        "session_open",
        "regular_interval_close",
        "closing_auction_close",
    ]
    price: float
    price_basis: Literal["as_printed", "split_adjusted"]
    algorithm_version: str
