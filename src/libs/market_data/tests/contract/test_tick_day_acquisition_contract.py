from collections.abc import Mapping
from typing import get_type_hints

from pytest import mark

from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.ports.fetch_historical_tick_payload_port import (
    FetchHistoricalTickPayloadPort,
)
from libs.market_data.ports.read_provider_traffic_usage_port import (
    ReadProviderTrafficUsagePort,
)
from libs.market_data.ports.tick_day_evidence_store_port import (
    TickDayEvidenceStorePort,
)


@mark.contract
def test_tick_day_acquisition_contract() -> None:
    assert ProviderTrafficUsage.__required_keys__ == frozenset(
        {
            "used_bytes",
            "limit_bytes",
            "remaining_bytes",
        }
    )
    usage_hints = get_type_hints(ProviderTrafficUsage)
    assert usage_hints["used_bytes"] is int
    assert usage_hints["limit_bytes"] is int
    assert usage_hints["remaining_bytes"] is int

    assert FetchHistoricalTickPayloadPort.__abstractmethods__ == frozenset(
        {"__call__"}
    )
    fetch_hints = get_type_hints(FetchHistoricalTickPayloadPort.__call__)
    assert fetch_hints["return"] == Mapping[str, object]

    assert ReadProviderTrafficUsagePort.__abstractmethods__ == frozenset(
        {"__call__"}
    )
    usage_port_hints = get_type_hints(ReadProviderTrafficUsagePort.__call__)
    assert usage_port_hints["return"] is ProviderTrafficUsage

    assert TickDayEvidenceStorePort.__abstractmethods__ == frozenset(
        {
            "__call__",
            "contains",
            "load_receipt",
        }
    )
