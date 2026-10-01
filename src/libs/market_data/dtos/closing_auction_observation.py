from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class ClosingAuctionObservation(TypedDict):
    security: SecurityIdentity
    session_date: date
    matched_at_utc: datetime
    price: float
    volume: float
    price_basis: Literal["as_printed", "split_adjusted"]
