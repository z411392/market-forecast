from datetime import date, time
from typing import Literal, TypedDict


class HistoricalTickRequestSpec(TypedDict):
    provider: Literal["shioaji"]
    source_symbol: str
    session_date: date
    query_type: Literal["RangeTime"]
    time_start_local: time
    time_end_local: time
