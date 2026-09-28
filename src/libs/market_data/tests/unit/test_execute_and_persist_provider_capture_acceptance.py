from datetime import date, datetime, timezone

from pytest import mark, raises

from libs.market_data.dtos.provider_capture_acceptance_receipt import (
    ProviderCaptureAcceptanceReceipt,
)
from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.ports.fetch_provider_raw_response_port import FetchProviderRawResponsePort
from libs.market_data.ports.persist_provider_capture_evidence_port import (
    PersistProviderCaptureEvidencePort,
)
from libs.market_data.services.execute_and_persist_provider_capture_acceptance import (
    execute_and_persist_provider_capture_acceptance,
)


class _FakeFetchProviderRawResponse(FetchProviderRawResponsePort):
    def __init__(self, raw_response: bytes | None = None, error: Exception | None = None) -> None:
        self.raw_response = raw_response
        self.error = error
        self.calls: list[tuple[str, ProviderRequestSpec]] = []

    def __call__(self, provider: str, request: ProviderRequestSpec) -> bytes:
        self.calls.append((provider, request))
        if self.error is not None:
            raise self.error
        if self.raw_response is None:
            raise AssertionError("missing fake raw response")
        return self.raw_response


class _FakePersistProviderCaptureEvidence(PersistProviderCaptureEvidencePort):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[bytes, ProviderCaptureAcceptanceReceipt]] = []

    def __call__(
        self,
        raw_response: bytes,
        receipt: ProviderCaptureAcceptanceReceipt,
    ) -> None:
        self.calls.append((raw_response, receipt))
        if self.error is not None:
            raise self.error


def _request() -> ProviderRequestSpec:
    return {
        "method": "GET",
        "path": "/v2/aggs/ticker/AAPL/range/1/minute/2025-11-26/2025-11-26",
        "query": (
            ("adjusted", "false"),
            ("sort", "asc"),
            ("limit", "50000"),
        ),
    }


def _security() -> SecurityIdentity:
    return {
        "symbol": "AAPL",
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _receipt(request: ProviderRequestSpec) -> ProviderCaptureAcceptanceReceipt:
    start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    return {
        "provider": "massive",
        "source_symbol": "AAPL",
        "security": _security(),
        "session_date": date(2025, 11, 26),
        "retrieval_date": date(2026, 9, 28),
        "request": request,
        "price_basis": "as_printed",
        "raw_artifact_sha256": "0" * 64,
        "expected_minute_count": 2,
        "observed_minute_count": 2,
        "first_bar_start_utc": start,
        "last_bar_start_utc": start,
        "gap_count": 0,
        "missing_grid_minutes": 0,
    }


@mark.unit
def test_execute_and_persist_provider_capture_acceptance(monkeypatch) -> None:
    request = _request()
    raw_response = b'{"status":"OK"}'
    receipt = _receipt(request)
    fetch = _FakeFetchProviderRawResponse(raw_response=raw_response)
    persist = _FakePersistProviderCaptureEvidence()
    acceptance_calls: list[bytes] = []

    def fake_build_provider_capture_acceptance(**kwargs) -> ProviderCaptureAcceptanceReceipt:
        acceptance_calls.append(kwargs["raw_response"])
        assert kwargs["request"] == request
        assert kwargs["provider"] == "massive"
        return receipt

    monkeypatch.setattr(
        "libs.market_data.services.execute_and_persist_provider_capture_acceptance."
        "build_provider_capture_acceptance",
        fake_build_provider_capture_acceptance,
    )

    actual = execute_and_persist_provider_capture_acceptance(
        fetch_raw_response=fetch,
        persist_evidence=persist,
        request=request,
        provider="massive",
        source_symbol="AAPL",
        retrieval_date=date(2026, 9, 28),
        security=_security(),
        session_date=date(2025, 11, 26),
        expected_session_start_utc=datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc),
        expected_session_end_utc_exclusive=datetime(2025, 11, 26, 14, 32, tzinfo=timezone.utc),
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert actual is receipt
    assert fetch.calls == [("massive", request)]
    assert acceptance_calls == [raw_response]
    assert acceptance_calls[0] is raw_response
    assert persist.calls == [(raw_response, receipt)]
    assert persist.calls[0][0] is raw_response

    failing_fetch = _FakeFetchProviderRawResponse(error=RuntimeError("fetch_failed"))
    persist_after_fetch_failure = _FakePersistProviderCaptureEvidence()
    with raises(RuntimeError, match="fetch_failed"):
        execute_and_persist_provider_capture_acceptance(
            fetch_raw_response=failing_fetch,
            persist_evidence=persist_after_fetch_failure,
            request=request,
            provider="massive",
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc),
            expected_session_end_utc_exclusive=datetime(2025, 11, 26, 14, 32, tzinfo=timezone.utc),
            expected_minute_count=2,
            price_basis="as_printed",
        )
    assert persist_after_fetch_failure.calls == []

    def failing_acceptance(**kwargs) -> ProviderCaptureAcceptanceReceipt:
        raise ValueError("acceptance_failed")

    monkeypatch.setattr(
        "libs.market_data.services.execute_and_persist_provider_capture_acceptance."
        "build_provider_capture_acceptance",
        failing_acceptance,
    )
    persist_after_acceptance_failure = _FakePersistProviderCaptureEvidence()
    with raises(ValueError, match="acceptance_failed"):
        execute_and_persist_provider_capture_acceptance(
            fetch_raw_response=fetch,
            persist_evidence=persist_after_acceptance_failure,
            request=request,
            provider="massive",
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc),
            expected_session_end_utc_exclusive=datetime(2025, 11, 26, 14, 32, tzinfo=timezone.utc),
            expected_minute_count=2,
            price_basis="as_printed",
        )
    assert persist_after_acceptance_failure.calls == []

    monkeypatch.setattr(
        "libs.market_data.services.execute_and_persist_provider_capture_acceptance."
        "build_provider_capture_acceptance",
        fake_build_provider_capture_acceptance,
    )
    persist_failure = _FakePersistProviderCaptureEvidence(error=RuntimeError("persist_failed"))
    with raises(RuntimeError, match="persist_failed"):
        execute_and_persist_provider_capture_acceptance(
            fetch_raw_response=fetch,
            persist_evidence=persist_failure,
            request=request,
            provider="massive",
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc),
            expected_session_end_utc_exclusive=datetime(2025, 11, 26, 14, 32, tzinfo=timezone.utc),
            expected_minute_count=2,
            price_basis="as_printed",
        )
    assert fetch.calls == [("massive", request), ("massive", request), ("massive", request)]
    assert persist_failure.calls == [(raw_response, receipt)]
