from typing import Literal, TypedDict

from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt


class TickBatchCollectionSummary(TypedDict):
    requested_count: int
    cache_hit_count: int
    acquired_count: int
    deferred_count: int
    receipts: tuple[TickDayEvidenceReceipt, ...]
    initial_usage: ProviderTrafficUsage | None
    final_usage: ProviderTrafficUsage | None
    current_run_delta_bytes: int
    stop_reason: Literal[
        "completed",
        "max_uncached_reached",
        "remaining_traffic_guard",
        "current_run_traffic_guard",
    ]
