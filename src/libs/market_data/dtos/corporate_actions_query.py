from datetime import date
from typing import TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class CorporateActionsQuery(TypedDict):
    security: SecurityIdentity
    start_date: date
    end_date: date
