from collections.abc import Mapping
from datetime import date, datetime, time, timezone
from typing import cast

from pytest import mark, raises

from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.exceptions.provider_capture_evidence_integrity_error import (
    ProviderCaptureEvidenceIntegrityError,
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
from libs.market_data.services.acquire_and_persist_tick_day_evidence import (
    acquire_and_persist_tick_day_evidence,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)


_MIN_REMAINING_BYTES = 250 * 1024 * 1024


def _request() -> HistoricalTickRequestSpec:
    return {
        "provider": "shioaji",
        "source_symbol": "2330",
        "session_date": date(2026, 9, 24),
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


def _provider_ns(hour: int, minute: int, second: int) -> int:
    wall_clock = datetime(
        2026,
        9,
        24,
        hour,
        minute,
        second,
        tzinfo=timezone.utc,
    )
    return int(wall_clock.timestamp()) * 1_000_000_000


def _payload() -> dict[str, object]:
    return {
        "ts": [
            _provider_ns(9, 0, 3),
            _provider_ns(9, 0, 3),
            _provider_ns(13, 30, 0),
        ],
        "close": [2480.0, 2480.5, 2475.0],
        "volume": [1000, 2000, 3000],
        "bid_price": [2475.0, 2480.0, 2470.0],
        "bid_volume": [10, 20, 30],
        "ask_price": [2480.0, 2480.5, 2475.0],
        "ask_volume": [11, 21, 31],
        "tick_type": [1, 1, 2],
    }


def _cached_receipt() -> TickDayEvidenceReceipt:
    request = _request()
    return {
        "provider": "shioaji",
        "provider_version": "1.7.7",
        "source_symbol": "2330",
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "request": request,
        "request_sha256": build_historical_tick_request_sha256(request),
        "sdk_observation_sha256": "1" * 64,
        "transaction_sequence_sha256": "2" * 64,
        "estimator_version": "tw-rk-parzen-trades-v1",
        "tick_count": 3,
        "first_observed_at_utc": datetime(
            2026,
            9,
            24,
            1,
            0,
            3,
            tzinfo=timezone.utc,
        ),
        "last_observed_at_utc": datetime(
            2026,
            9,
            24,
            5,
            30,
            0,
            tzinfo=timezone.utc,
        ),
        "opening_price": 2480.0,
        "closing_auction_observed_at_utc": datetime(
            2026,
            9,
            24,
            5,
            30,
            0,
            tzinfo=timezone.utc,
        ),
        "closing_auction_price": 2475.0,
        "duplicate_timestamp_adjacency_count": 1,
    }


class _FakeFetch(FetchHistoricalTickPayloadPort):
    def __init__(
        self,
        payload: Mapping[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or _payload()
        self.error = error
        self.calls: list[HistoricalTickRequestSpec] = []

    def __call__(
        self,
        request: HistoricalTickRequestSpec,
    ) -> Mapping[str, object]:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.payload


class _FakeUsage(ReadProviderTrafficUsagePort):
    def __init__(self, remaining_bytes: int) -> None:
        self.calls = 0
        self.usage: ProviderTrafficUsage = {
            "used_bytes": 10 * 1024 * 1024,
            "limit_bytes": 500 * 1024 * 1024,
            "remaining_bytes": remaining_bytes,
        }

    def __call__(self) -> ProviderTrafficUsage:
        self.calls += 1
        return self.usage


class _FakeStore(TickDayEvidenceStorePort):
    def __init__(
        self,
        receipt: TickDayEvidenceReceipt | None = None,
        *,
        contains_override: bool | None = None,
    ) -> None:
        self.receipt = receipt
        self.contains_override = contains_override
        self.persist_calls: list[
            tuple[bytes, bytes, TickDayEvidenceReceipt]
        ] = []

    def contains(self, request_sha256: str) -> bool:
        if self.contains_override is not None:
            return self.contains_override
        return (
            self.receipt is not None
            and self.receipt["request_sha256"] == request_sha256
        )

    def load_receipt(
        self,
        request_sha256: str,
    ) -> TickDayEvidenceReceipt | None:
        if (
            self.receipt is not None
            and self.receipt["request_sha256"] == request_sha256
        ):
            return self.receipt
        return None

    def __call__(
        self,
        sdk_observation: bytes,
        transaction_sequence: bytes,
        receipt: TickDayEvidenceReceipt,
    ) -> None:
        self.persist_calls.append(
            (sdk_observation, transaction_sequence, receipt)
        )
        self.receipt = receipt


@mark.unit
def test_acquire_tick_day_is_cache_first_and_persists_one_miss() -> None:
    request = _request()
    fetch = _FakeFetch()
    usage = _FakeUsage(remaining_bytes=400 * 1024 * 1024)
    store = _FakeStore()

    receipt = acquire_and_persist_tick_day_evidence(
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        request=request,
        security=_security(),
        provider_version="1.7.7",
    )

    assert usage.calls == 1
    assert fetch.calls == [request]
    assert len(store.persist_calls) == 1
    assert receipt == store.receipt
    assert receipt["request_sha256"] == build_historical_tick_request_sha256(
        request
    )
    assert receipt["tick_count"] == 3
    assert receipt["opening_price"] == 2480.0
    assert receipt["closing_auction_price"] == 2475.0
    assert receipt["duplicate_timestamp_adjacency_count"] == 1

    cached = acquire_and_persist_tick_day_evidence(
        fetch_payload=fetch,
        read_usage=usage,
        evidence_store=store,
        request=request,
        security=_security(),
        provider_version="1.7.7",
    )
    assert cached == receipt
    assert usage.calls == 1
    assert fetch.calls == [request]
    assert len(store.persist_calls) == 1


@mark.unit
def test_acquire_tick_day_fails_before_fetch_when_traffic_is_low() -> None:
    fetch = _FakeFetch()
    usage = _FakeUsage(remaining_bytes=_MIN_REMAINING_BYTES - 1)
    store = _FakeStore()

    with raises(ProviderTransportError):
        acquire_and_persist_tick_day_evidence(
            fetch_payload=fetch,
            read_usage=usage,
            evidence_store=store,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )

    assert usage.calls == 1
    assert fetch.calls == []
    assert store.persist_calls == []


@mark.unit
def test_acquire_tick_day_rejects_corrupt_cache_without_fetch() -> None:
    fetch = _FakeFetch()
    usage = _FakeUsage(remaining_bytes=400 * 1024 * 1024)
    store = _FakeStore(contains_override=True)

    with raises(ProviderCaptureEvidenceIntegrityError):
        acquire_and_persist_tick_day_evidence(
            fetch_payload=fetch,
            read_usage=usage,
            evidence_store=store,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )

    assert usage.calls == 0
    assert fetch.calls == []
    assert store.persist_calls == []


@mark.unit
def test_acquire_tick_day_does_not_persist_failed_fetch_or_decode() -> None:
    usage = _FakeUsage(remaining_bytes=400 * 1024 * 1024)

    fetch_error = _FakeFetch(error=ProviderTransportError("provider_failed"))
    fetch_store = _FakeStore()
    with raises(ProviderTransportError):
        acquire_and_persist_tick_day_evidence(
            fetch_payload=fetch_error,
            read_usage=usage,
            evidence_store=fetch_store,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )
    assert fetch_store.persist_calls == []

    invalid_payload = cast(dict[str, object], _payload())
    del invalid_payload["tick_type"]
    decode_store = _FakeStore()
    with raises(InvalidProviderCaptureInputError):
        acquire_and_persist_tick_day_evidence(
            fetch_payload=_FakeFetch(payload=invalid_payload),
            read_usage=_FakeUsage(remaining_bytes=400 * 1024 * 1024),
            evidence_store=decode_store,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )
    assert decode_store.persist_calls == []
