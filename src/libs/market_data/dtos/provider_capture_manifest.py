from datetime import date, datetime
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class ProviderCaptureManifest(TypedDict):
    provider: Literal["massive", "finmind", "alpaca"]
    source_symbol: str
    retrieval_date: date
    security: SecurityIdentity
    session_date: date
    expected_session_start_utc: datetime
    expected_session_end_utc_exclusive: datetime
    expected_minute_count: int
    price_basis: Literal["as_printed", "split_adjusted"]
    raw_artifact_sha256: str
