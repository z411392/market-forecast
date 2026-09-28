from datetime import date, datetime
from typing import TypedDict


class SourceProvenance(TypedDict):
    provider: str
    provider_dataset: str
    source_symbol: str
    requested_start_session_date: date
    requested_end_session_date: date
    retrieved_at_utc: datetime
    raw_artifact_id: str
    raw_content_sha256: str
