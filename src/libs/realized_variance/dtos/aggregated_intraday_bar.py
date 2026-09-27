from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class AggregatedIntradayBar(TypedDict):
    security: SecurityIdentity
    session_date: date
    bar_start_utc: datetime
    interval_minutes: Literal[5, 10, 15]
    open: float
    high: float
    low: float
    close: float
    volume: float
    price_basis: Literal["as_printed", "split_adjusted"]
    source_minute_count: int
    algorithm_version: str
