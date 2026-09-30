from typing import get_args, get_type_hints

from pytest import mark

from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_batch_collection_summary import (
    TickBatchCollectionSummary,
)
from libs.market_data.dtos.tick_day_collection_item import TickDayCollectionItem
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt


@mark.contract
def test_tick_batch_collection_contract() -> None:
    assert TickDayCollectionItem.__required_keys__ == frozenset(
        {
            "request",
            "security",
        }
    )
    item_hints = get_type_hints(TickDayCollectionItem)
    assert item_hints["request"] is HistoricalTickRequestSpec
    assert item_hints["security"] is SecurityIdentity

    assert TickBatchCollectionSummary.__required_keys__ == frozenset(
        {
            "requested_count",
            "cache_hit_count",
            "acquired_count",
            "deferred_count",
            "receipts",
            "initial_usage",
            "final_usage",
            "current_run_delta_bytes",
            "stop_reason",
        }
    )
    summary_hints = get_type_hints(TickBatchCollectionSummary)
    assert summary_hints["requested_count"] is int
    assert summary_hints["cache_hit_count"] is int
    assert summary_hints["acquired_count"] is int
    assert summary_hints["deferred_count"] is int
    assert summary_hints["receipts"] == tuple[TickDayEvidenceReceipt, ...]
    assert get_args(summary_hints["initial_usage"]) == (
        ProviderTrafficUsage,
        type(None),
    )
    assert get_args(summary_hints["final_usage"]) == (
        ProviderTrafficUsage,
        type(None),
    )
    assert summary_hints["current_run_delta_bytes"] is int
    assert get_args(summary_hints["stop_reason"]) == (
        "completed",
        "max_uncached_reached",
        "remaining_traffic_guard",
        "current_run_traffic_guard",
    )
