from datetime import date, datetime, time
from typing import get_args, get_type_hints

from pytest import mark

from libs.market_data.dtos.canonical_transaction_tick import CanonicalTransactionTick
from libs.market_data.dtos.historical_tick_request_spec import HistoricalTickRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt


@mark.contract
def test_historical_tick_request_spec_contract() -> None:
    assert HistoricalTickRequestSpec.__required_keys__ == frozenset(
        {
            "provider",
            "source_symbol",
            "session_date",
            "query_type",
            "time_start_local",
            "time_end_local",
        }
    )

    hints = get_type_hints(HistoricalTickRequestSpec)
    assert get_args(hints["provider"]) == ("shioaji",)
    assert hints["source_symbol"] is str
    assert hints["session_date"] is date
    assert get_args(hints["query_type"]) == ("RangeTime",)
    assert hints["time_start_local"] is time
    assert hints["time_end_local"] is time


@mark.contract
def test_canonical_transaction_tick_contract() -> None:
    assert CanonicalTransactionTick.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "observed_at_utc",
            "price",
            "volume",
        }
    )

    hints = get_type_hints(CanonicalTransactionTick)
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert hints["observed_at_utc"] is datetime
    assert hints["price"] is float
    assert hints["volume"] is float


@mark.contract
def test_tick_day_evidence_receipt_contract() -> None:
    assert TickDayEvidenceReceipt.__required_keys__ == frozenset(
        {
            "provider",
            "provider_version",
            "source_symbol",
            "security",
            "session_date",
            "request",
            "request_sha256",
            "sdk_observation_sha256",
            "transaction_sequence_sha256",
            "estimator_version",
            "tick_count",
            "first_observed_at_utc",
            "last_observed_at_utc",
            "opening_price",
            "closing_auction_observed_at_utc",
            "closing_auction_price",
            "duplicate_timestamp_adjacency_count",
        }
    )

    hints = get_type_hints(TickDayEvidenceReceipt)
    assert get_args(hints["provider"]) == ("shioaji",)
    assert hints["provider_version"] is str
    assert hints["source_symbol"] is str
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert hints["request"] is HistoricalTickRequestSpec
    assert hints["request_sha256"] is str
    assert hints["sdk_observation_sha256"] is str
    assert hints["transaction_sequence_sha256"] is str
    assert hints["estimator_version"] is str
    assert hints["tick_count"] is int
    assert hints["first_observed_at_utc"] is datetime
    assert hints["last_observed_at_utc"] is datetime
    assert hints["opening_price"] is float
    assert hints["closing_auction_observed_at_utc"] is datetime
    assert hints["closing_auction_price"] is float
    assert hints["duplicate_timestamp_adjacency_count"] is int
