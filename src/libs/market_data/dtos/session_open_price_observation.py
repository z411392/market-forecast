from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class SessionOpenPriceObservation(TypedDict):
    security: SecurityIdentity
    session_date: date
    source_interval_start_utc: datetime
    price: float
    price_basis: Literal["as_printed", "split_adjusted"]
