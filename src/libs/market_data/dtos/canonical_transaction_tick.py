from datetime import date, datetime
from typing import TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class CanonicalTransactionTick(TypedDict):
    security: SecurityIdentity
    session_date: date
    observed_at_utc: datetime
    price: float
    volume: float
