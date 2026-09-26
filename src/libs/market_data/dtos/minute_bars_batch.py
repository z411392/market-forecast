from typing import TypedDict

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.minute_bars_query import MinuteBarsQuery
from libs.market_data.dtos.source_provenance import SourceProvenance


class MinuteBarsBatch(TypedDict):
    query: MinuteBarsQuery
    provenance: SourceProvenance
    bars: tuple[CanonicalMinuteBar, ...]
