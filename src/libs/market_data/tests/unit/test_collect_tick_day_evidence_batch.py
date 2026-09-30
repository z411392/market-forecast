from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, timezone

from pytest import mark, raises

from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_collection_item import TickDayCollectionItem
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError
from libs.market_data.ports.fetch_historical_tick_payload_port import (
    FetchHistoricalTickPayloadPort,
)
from libs.market_data.ports.read_provider_traffic_usage_port import (
    ReadProviderTrafficUsagePort,
)
from libs.market_data.ports.tick_day_evidence_store_port import (
    TickDayEvidenceStorePort,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)
from libs.market_data.services.collect_tick_day_evidence_batch import (
    collect_tick_day_evidence_batch,
)


_MIB = 1024 * 1024


def _request(index: int) -> HistoricalTickRequestSpec:
    return {
        "provider": "shioaji",
        "source_symbol": "2330",
        "session_date": date(2026, 1, 1) + timedelta(days=index),
        "query_type": "RangeTime",
        "time_start_local": time(9, 0),
        "time_end_local": time(13, 30, 59),
    }


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _item(index: int) -> TickDayCollectionItem:
    return {
        "request": _request(index),
        "security": _security(),
    }


def _provider_ns(session_date: date, hour: int, minute: int, second: int) -> int:
    wall_clock = datetime(
        session_date.year,
        session_date.month,
        session_date.day,
        hour,
        minute,
        second,
        tzinfo=timezone.utc,
    )
    return int(wall_clock.timestamp()) * 1_000_000_000


def _payload(request: HistoricalTickRequestSpec) -> dict[str, object]:
    session_date = request["session_date"]
    return {
        "ts": [
            _provider_ns(session_date, 9, 0, 3),
            _provider_ns(session_date, 13, 30, 0),
        ],
        "close": [100.0, 101.0],
        "volume": [1, 2],
        "bid_price": [99.5, 100.5],
        "bid_volume": [10, 20],
        "ask_price": [100.0, 101.0],
        "ask_volume": [11, 21],
        "tick_type": [1, 2],
    }


def _cached_receipt(item: TickDayCollectionItem) -> TickDayEvidenceReceipt:
    request = item["request"]
    session_date = request["session_date"]
    request_sha = build_historical_tick_request_sha256(request)
    return {
        "provider": "shioaji",
        "provider_version": "1.7.7",
        "source_symbol": request["source_symbol"],
        "security": item["security"],
        "session_date": session_date,
        "request": request,
        "request_sha256": request_sha,
        "sdk_observation_sha256": "1" * 64,
        "transaction_sequence_sha256": "2" * 64,
        "estimator_version": "tw-rk-parzen-trades-v1",
        "tick_count": 2,
        "first_observed_at_utc": datetime(
            session_date.year,
            session_date.month,
            session_date.day,
            1,
            0,
            3,
            tzinfo=timezone.utc,
        ),
        "last_observed_at_utc": datetime(
            session_date.year,
            session_date.month,
            session_date.day,
            5,
            30,
            0,
            tzinfo=timezone.utc,
        ),
        "opening_price": 100.0,
        "closing_auction_observed_at_utc": datetime(
            session_date.year,
            session_date.month,
            session_date.day,
            5,
            30,
            0,
            tzinfo=timezone.utc,
        ),
        "closing_auction_price": 101.0,
        "duplicate_timestamp_adjacency_count": 0,
    }


def _usage(
    *,
    used_mib: int = 10,
    remaining_mib: int = 400,
) -> ProviderTrafficUsage:
    return {
        "used_bytes": used_mib * _MIB,
        "limit_bytes": 500 * _MIB,
        "remaining_bytes": remaining_mib * _MIB,
    }


class _FakeFetch(FetchHistoricalTickPayloadPort):
    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls: list[HistoricalTickRequestSpec] = []

    def __call__(
        self,
        request: HistoricalTickRequestSpec,
    ) -> Mapping[str, object]:
        self.calls.append(request)
        if self.fail_on_call == len(self.calls):
            raise ProviderTransportError("provider_failed")
        return _payload(request)


class _SequenceUsage(ReadProviderTrafficUsagePort):
    def __init__(self, snapshots: list[ProviderTrafficUsage]) -> None:
        self.snapshots = snapshots
        self.calls = 0

    def __call__(self) -> ProviderTrafficUsage:
        if not self.snapshots:
            raise AssertionError("usage should not be called")
        index = min(self.calls, len(self.snapshots) - 1)
        self.calls += 1
        return self.snapshots[index]


class _FakeStore(TickDayEvidenceStorePort):
    def __init__(
        self,
        receipts: tuple[TickDayEvidenceReceipt, ...] = (),
    ) -> None:
        self.receipts = {
            receipt["request_sha256"]: receipt for receipt in receipts
        }
        self.persist_calls: list[
            tuple[bytes, bytes, TickDayEvidenceReceipt]
        ] = []

    def contains(self, request_sha256: str) -> bool:
        return request_sha256 in self.receipts

    def load_receipt(
        self,
        request_sha256: str,
    ) -> TickDayEvidenceReceipt | None:
        return self.receipts.get(request_sha256)

    def __call__(
        self,
        sdk_observation: bytes,
        transaction_sequence: bytes,
        receipt: TickDayEvidenceReceipt,
    ) -> None:
        self.persist_calls.append(
            (sdk_observation, transaction_sequence, receipt)
        )
        self.receipts[receipt["request_sha256"]] = receipt


@mark.unit
def test_collect_batch_is_cache_first_with_zero_provider_access_when_all_cached() -> None:
    items = tuple(_item(index) for index in range(3))
    store = _FakeStore(tuple(_cached_receipt(item) for item in items))
    fetch = _FakeFetch()
    usage = _SequenceUsage([])

    result = collect_tick_day_evidence_batch(
        items=items,
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        provider_version="1.7.7",
    )

    assert result["requested_count"] == 3
    assert result["cache_hit_count"] == 3
    assert result["acquired_count"] == 0
    assert result["deferred_count"] == 0
    assert result["stop_reason"] == "completed"
    assert result["initial_usage"] is None
    assert result["final_usage"] is None
    assert result["current_run_delta_bytes"] == 0
    assert tuple(receipt["session_date"] for receipt in result["receipts"]) == tuple(
        item["request"]["session_date"] for item in items
    )
    assert usage.calls == 0
    assert fetch.calls == []
    assert store.persist_calls == []


@mark.unit
def test_collect_batch_preserves_order_for_mixed_cache_hits_and_misses() -> None:
    items = tuple(_item(index) for index in range(4))
    store = _FakeStore(
        (
            _cached_receipt(items[0]),
            _cached_receipt(items[2]),
        )
    )
    fetch = _FakeFetch()
    usage = _SequenceUsage(
        [
            _usage(used_mib=10),
            _usage(used_mib=10),
            _usage(used_mib=11),
            _usage(used_mib=11),
            _usage(used_mib=11),
            _usage(used_mib=12),
        ]
    )

    result = collect_tick_day_evidence_batch(
        items=items,
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        provider_version="1.7.7",
    )

    assert result["stop_reason"] == "completed"
    assert result["cache_hit_count"] == 2
    assert result["acquired_count"] == 2
    assert result["deferred_count"] == 0
    assert tuple(receipt["session_date"] for receipt in result["receipts"]) == tuple(
        item["request"]["session_date"] for item in items
    )
    assert fetch.calls == [
        items[1]["request"],
        items[3]["request"],
    ]
    assert len(store.persist_calls) == 2
    assert usage.calls == 6
    assert result["current_run_delta_bytes"] == 2 * _MIB


@mark.unit
def test_collect_batch_caps_uncached_acquisitions_at_100() -> None:
    items = tuple(_item(index) for index in range(101))
    store = _FakeStore()
    fetch = _FakeFetch()
    usage = _SequenceUsage([_usage()])

    result = collect_tick_day_evidence_batch(
        items=items,
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        provider_version="1.7.7",
    )

    assert result["stop_reason"] == "max_uncached_reached"
    assert result["cache_hit_count"] == 0
    assert result["acquired_count"] == 100
    assert result["deferred_count"] == 1
    assert len(result["receipts"]) == 100
    assert len(fetch.calls) == 100
    assert len(store.persist_calls) == 100


@mark.unit
def test_collect_batch_stops_before_fetch_when_remaining_traffic_is_low() -> None:
    items = (_item(0), _item(1))
    store = _FakeStore()
    fetch = _FakeFetch()
    low = _usage(remaining_mib=99)
    usage = _SequenceUsage([low])

    result = collect_tick_day_evidence_batch(
        items=items,
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        provider_version="1.7.7",
    )

    assert result["stop_reason"] == "remaining_traffic_guard"
    assert result["acquired_count"] == 0
    assert result["deferred_count"] == 2
    assert result["initial_usage"] == low
    assert result["final_usage"] == low
    assert result["current_run_delta_bytes"] == 0
    assert fetch.calls == []
    assert store.persist_calls == []


@mark.unit
def test_collect_batch_stops_after_persist_when_current_run_delta_reaches_guard() -> None:
    items = (_item(0), _item(1))
    store = _FakeStore()
    fetch = _FakeFetch()
    usage = _SequenceUsage(
        [
            _usage(used_mib=10, remaining_mib=400),
            _usage(used_mib=10, remaining_mib=400),
            _usage(used_mib=260, remaining_mib=300),
        ]
    )

    result = collect_tick_day_evidence_batch(
        items=items,
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        provider_version="1.7.7",
    )

    assert result["stop_reason"] == "current_run_traffic_guard"
    assert result["acquired_count"] == 1
    assert result["deferred_count"] == 1
    assert len(fetch.calls) == 1
    assert len(store.persist_calls) == 1
    assert result["current_run_delta_bytes"] == 250 * _MIB


@mark.unit
def test_collect_batch_can_read_cached_items_after_provider_stop() -> None:
    items = (_item(0), _item(1), _item(2))
    cached = _cached_receipt(items[2])
    store = _FakeStore((cached,))
    fetch = _FakeFetch()
    usage = _SequenceUsage(
        [
            _usage(used_mib=10, remaining_mib=400),
            _usage(used_mib=10, remaining_mib=400),
            _usage(used_mib=260, remaining_mib=300),
        ]
    )

    result = collect_tick_day_evidence_batch(
        items=items,
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        provider_version="1.7.7",
    )

    assert result["stop_reason"] == "current_run_traffic_guard"
    assert result["cache_hit_count"] == 1
    assert result["acquired_count"] == 1
    assert result["deferred_count"] == 1
    assert tuple(receipt["session_date"] for receipt in result["receipts"]) == (
        items[0]["request"]["session_date"],
        items[2]["request"]["session_date"],
    )
    assert len(fetch.calls) == 1


@mark.unit
def test_collect_batch_rejects_decreasing_usage_counter_after_persist() -> None:
    item = _item(0)
    store = _FakeStore()
    fetch = _FakeFetch()
    usage = _SequenceUsage(
        [
            _usage(used_mib=100, remaining_mib=350),
            _usage(used_mib=100, remaining_mib=350),
            _usage(used_mib=90, remaining_mib=350),
        ]
    )

    with raises(ProviderTransportError):
        collect_tick_day_evidence_batch(
            items=(item,),
            fetch_payload=fetch,
            read_usage=usage,
            evidence_store=store,
            provider_version="1.7.7",
        )

    assert len(fetch.calls) == 1
    assert len(store.persist_calls) == 1


@mark.unit
def test_collect_batch_stops_on_provider_failure_without_later_fetches() -> None:
    items = (_item(0), _item(1))
    store = _FakeStore()
    fetch = _FakeFetch(fail_on_call=1)
    usage = _SequenceUsage([_usage()])

    with raises(ProviderTransportError):
        collect_tick_day_evidence_batch(
            items=items,
            fetch_payload=fetch,
            read_usage=usage,
            evidence_store=store,
            provider_version="1.7.7",
        )

    assert fetch.calls == [items[0]["request"]]
    assert store.persist_calls == []


@mark.unit
def test_collect_batch_rejects_invalid_plan_before_provider_access() -> None:
    first = _item(0)
    duplicate = {
        "request": dict(first["request"]),
        "security": first["security"],
    }
    mismatched = {
        "request": _request(1),
        "security": {
            **_security(),
            "symbol": "2317",
        },
    }

    for items in ((first, duplicate), (mismatched,)):
        usage = _SequenceUsage([])
        fetch = _FakeFetch()
        with raises(InvalidProviderCaptureInputError):
            collect_tick_day_evidence_batch(
                items=items,
                fetch_payload=fetch,
                read_usage=usage,
                evidence_store=_FakeStore(),
                provider_version="1.7.7",
            )
        assert usage.calls == 0
        assert fetch.calls == []
