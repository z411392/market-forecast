from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity


class ProviderCaptureAcceptanceReceipt(TypedDict):
    provider: Literal["massive", "finmind"]
    source_symbol: str
    security: SecurityIdentity
    session_date: date
    retrieval_date: date
    request: ProviderRequestSpec
    price_basis: Literal["as_printed", "split_adjusted"]
    raw_artifact_sha256: str
    expected_minute_count: int
    observed_minute_count: int
    first_bar_start_utc: datetime
    last_bar_start_utc: datetime
    gap_count: int
    missing_grid_minutes: int
