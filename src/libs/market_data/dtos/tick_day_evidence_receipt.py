from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.historical_tick_request_spec import HistoricalTickRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity


class TickDayEvidenceReceipt(TypedDict):
    provider: Literal["shioaji"]
    provider_version: str
    source_symbol: str
    security: SecurityIdentity
    session_date: date
    request: HistoricalTickRequestSpec
    request_sha256: str
    sdk_observation_sha256: str
    transaction_sequence_sha256: str
    estimator_version: str
    tick_count: int
    first_observed_at_utc: datetime
    last_observed_at_utc: datetime
    opening_price: float
    closing_auction_observed_at_utc: datetime
    closing_auction_price: float
    duplicate_timestamp_adjacency_count: int
