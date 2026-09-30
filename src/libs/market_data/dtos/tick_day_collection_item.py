from typing import TypedDict

from libs.market_data.dtos.historical_tick_request_spec import HistoricalTickRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity


class TickDayCollectionItem(TypedDict):
    request: HistoricalTickRequestSpec
    security: SecurityIdentity
