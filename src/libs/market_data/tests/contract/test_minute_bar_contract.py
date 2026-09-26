from datetime import date, datetime
from typing import get_args, get_origin, get_type_hints

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.minute_bars_batch import MinuteBarsBatch
from libs.market_data.dtos.minute_bars_query import MinuteBarsQuery
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.source_provenance import SourceProvenance
from pytest import mark


@mark.contract
def test_minute_bar_contract() -> None:
    assert SecurityIdentity.__required_keys__ == frozenset(
        {"symbol", "exchange", "timezone", "calendar_id"}
    )
    assert get_type_hints(SecurityIdentity) == {
        "symbol": str,
        "exchange": str,
        "timezone": str,
        "calendar_id": str,
    }

    query_hints = get_type_hints(MinuteBarsQuery)
    assert MinuteBarsQuery.__required_keys__ == frozenset(
        {"security", "start_session_date", "end_session_date", "session_scope"}
    )
    assert query_hints["security"] is SecurityIdentity
    assert query_hints["start_session_date"] is date
    assert query_hints["end_session_date"] is date
    assert get_args(query_hints["session_scope"]) == ("regular", "all_observed")

    assert SourceProvenance.__required_keys__ == frozenset(
        {
            "provider",
            "provider_dataset",
            "source_symbol",
            "requested_start_session_date",
            "requested_end_session_date",
            "retrieved_at_utc",
            "raw_artifact_id",
            "raw_content_sha256",
        }
    )
    provenance_hints = get_type_hints(SourceProvenance)
    assert provenance_hints["provider"] is str
    assert provenance_hints["provider_dataset"] is str
    assert provenance_hints["source_symbol"] is str
    assert provenance_hints["requested_start_session_date"] is date
    assert provenance_hints["requested_end_session_date"] is date
    assert provenance_hints["retrieved_at_utc"] is datetime
    assert provenance_hints["raw_artifact_id"] is str
    assert provenance_hints["raw_content_sha256"] is str
    assert "adjusted" not in provenance_hints

    assert CanonicalMinuteBar.__required_keys__ == frozenset(
        {
            "security",
            "bar_start_utc",
            "session_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "price_basis",
        }
    )
    bar_hints = get_type_hints(CanonicalMinuteBar)
    assert bar_hints["security"] is SecurityIdentity
    assert bar_hints["bar_start_utc"] is datetime
    assert bar_hints["session_date"] is date
    assert bar_hints["open"] is float
    assert bar_hints["high"] is float
    assert bar_hints["low"] is float
    assert bar_hints["close"] is float
    assert bar_hints["volume"] is float
    assert get_args(bar_hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert "adjusted" not in bar_hints

    assert MinuteBarsBatch.__required_keys__ == frozenset({"query", "provenance", "bars"})
    batch_hints = get_type_hints(MinuteBarsBatch)
    assert batch_hints["query"] is MinuteBarsQuery
    assert batch_hints["provenance"] is SourceProvenance
    assert get_origin(batch_hints["bars"]) is tuple
    assert get_args(batch_hints["bars"]) == (CanonicalMinuteBar, Ellipsis)
