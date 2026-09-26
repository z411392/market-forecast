from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class MinuteBarsQuery(TypedDict):
    security: SecurityIdentity
    start_session_date: date
    end_session_date: date
    session_scope: Literal["regular", "all_observed"]
