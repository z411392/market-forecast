from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class CanonicalMinuteBar(TypedDict):
    security: SecurityIdentity
    bar_start_utc: datetime
    session_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    price_basis: Literal["as_printed", "split_adjusted"]
