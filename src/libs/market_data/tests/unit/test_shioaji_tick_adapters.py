from collections.abc import Mapping
from datetime import date, time
from typing import Any

from pytest import mark, raises

from libs.market_data.adapters.driven.shioaji_historical_tick_payload_adapter import (
    ShioajiHistoricalTickPayloadAdapter,
)
from libs.market_data.adapters.driven.shioaji_provider_traffic_usage_adapter import (
    ShioajiProviderTrafficUsageAdapter,
)
from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError


def _request(
    *,
    symbol: str = "2330",
    session_date: date = date(2026, 9, 24),
) -> HistoricalTickRequestSpec:
    return {
        "provider": "shioaji",
        "source_symbol": symbol,
        "session_date": session_date,
        "query_type": "RangeTime",
        "time_start_local": time(9, 0),
        "time_end_local": time(13, 30, 59),
    }


class _Result:
    def __init__(self, payload: Mapping[str, object]) -> None:
        self.payload = payload

    def dict(self) -> Mapping[str, object]:
        return self.payload


class _Contracts:
    def __init__(self, contracts: dict[str, object]) -> None:
        self.contracts = contracts
        self.calls: list[str] = []

    def get(self, symbol: str) -> object | None:
        self.calls.append(symbol)
        return self.contracts.get(symbol)


class _Usage:
    def __init__(
        self,
        *,
        used_bytes: object,
        limit_bytes: object,
        remaining_bytes: object,
    ) -> None:
        self.bytes = used_bytes
        self.limit_bytes = limit_bytes
        self.remaining_bytes = remaining_bytes


class _Api:
    def __init__(
        self,
        *,
        contracts: dict[str, object] | None = None,
        payload: Mapping[str, object] | None = None,
        usage: object | None = None,
        tick_error: Exception | None = None,
        usage_error: Exception | None = None,
    ) -> None:
        self.contracts = _Contracts(
            {"2330": object()} if contracts is None else contracts
        )
        self.payload = payload or {"ts": [1], "close": [1.0]}
        self.usage_value = usage or _Usage(
            used_bytes=10,
            limit_bytes=500,
            remaining_bytes=490,
        )
        self.tick_error = tick_error
        self.usage_error = usage_error
        self.tick_calls: list[dict[str, Any]] = []
        self.usage_calls = 0

    def ticks(self, **kwargs: Any) -> _Result:
        self.tick_calls.append(kwargs)
        if self.tick_error is not None:
            raise self.tick_error
        return _Result(self.payload)

    def usage(self) -> object:
        self.usage_calls += 1
        if self.usage_error is not None:
            raise self.usage_error
        return self.usage_value


@mark.unit
def test_shioaji_historical_tick_adapter_maps_exact_request_and_caches_contract() -> None:
    contract = object()
    api = _Api(contracts={"2330": contract})
    adapter = ShioajiHistoricalTickPayloadAdapter(
        api,
        range_time_query_type="RANGE",
        timeout_ms=15000,
    )

    first = adapter(_request())
    second = adapter(_request(session_date=date(2026, 9, 23)))

    assert first == api.payload
    assert second == api.payload
    assert api.contracts.calls == ["2330"]
    assert api.tick_calls == [
        {
            "contract": contract,
            "date": "2026-09-24",
            "query_type": "RANGE",
            "time_start": time(9, 0),
            "time_end": time(13, 30, 59),
            "timeout": 15000,
        },
        {
            "contract": contract,
            "date": "2026-09-23",
            "query_type": "RANGE",
            "time_start": time(9, 0),
            "time_end": time(13, 30, 59),
            "timeout": 15000,
        },
    ]


@mark.unit
def test_shioaji_historical_tick_adapter_fails_closed() -> None:
    missing_contract = ShioajiHistoricalTickPayloadAdapter(
        _Api(contracts={}),
        range_time_query_type="RANGE",
    )
    with raises(ProviderTransportError):
        missing_contract(_request())

    provider_error = ShioajiHistoricalTickPayloadAdapter(
        _Api(tick_error=RuntimeError("provider failed")),
        range_time_query_type="RANGE",
    )
    with raises(ProviderTransportError):
        provider_error(_request())

    class _BadApi(_Api):
        def ticks(self, **kwargs: Any) -> object:
            self.tick_calls.append(kwargs)
            return object()

    invalid_result = ShioajiHistoricalTickPayloadAdapter(
        _BadApi(),
        range_time_query_type="RANGE",
    )
    with raises(ProviderTransportError):
        invalid_result(_request())


@mark.unit
def test_shioaji_usage_adapter_normalizes_only_cumulative_fields() -> None:
    api = _Api(
        usage=_Usage(
            used_bytes=22_287_469,
            limit_bytes=524_288_000,
            remaining_bytes=502_000_531,
        )
    )
    adapter = ShioajiProviderTrafficUsageAdapter(api)

    assert adapter() == {
        "used_bytes": 22_287_469,
        "limit_bytes": 524_288_000,
        "remaining_bytes": 502_000_531,
    }
    assert api.usage_calls == 1


@mark.unit
def test_shioaji_usage_adapter_rejects_invalid_or_failed_usage() -> None:
    invalid_values = (
        _Usage(used_bytes=True, limit_bytes=500, remaining_bytes=499),
        _Usage(used_bytes=-1, limit_bytes=500, remaining_bytes=501),
        _Usage(used_bytes=10, limit_bytes=0, remaining_bytes=0),
        _Usage(used_bytes=501, limit_bytes=500, remaining_bytes=0),
        _Usage(used_bytes=10, limit_bytes=500, remaining_bytes=501),
    )
    for usage in invalid_values:
        with raises(ProviderTransportError):
            ShioajiProviderTrafficUsageAdapter(_Api(usage=usage))()

    with raises(ProviderTransportError):
        ShioajiProviderTrafficUsageAdapter(
            _Api(usage_error=RuntimeError("usage failed"))
        )()
