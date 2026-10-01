import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from pytest import mark, raises

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.ports.fetch_provider_raw_response_port import FetchProviderRawResponsePort
from libs.market_data.services.build_massive_regular_session_minute_request import (
    build_massive_regular_session_minute_request,
)
from libs.market_data.services.execute_provider_capture_acceptance import (
    execute_provider_capture_acceptance,
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


def _security() -> SecurityIdentity:
    return {
        "symbol": "AAPL",
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _raw_response() -> bytes:
    start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    return json.dumps(
        {
            "ticker": "AAPL",
            "adjusted": False,
            "status": "OK",
            "results": [
                {
                    "o": 100.0 + index,
                    "h": 101.0 + index,
                    "l": 99.0 + index,
                    "c": 100.5 + index,
                    "v": 1000.0 + index,
                    "t": int((start + timedelta(minutes=index)).timestamp() * 1000),
                }
                for index in range(2)
            ],
        },
        separators=(",", ":"),
    ).encode()


@mark.unit
def test_execute_provider_capture_acceptance() -> None:
    session_date = date(2025, 11, 26)
    retrieval_date = date(2026, 9, 28)
    start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    request = build_massive_regular_session_minute_request(
        source_symbol="AAPL",
        session_start_utc=start,
        session_end_utc_exclusive=start + timedelta(minutes=2),
        price_basis="as_printed",
    )
    raw_response = _raw_response()
    fetch = _FakeFetchProviderRawResponse(raw_response=raw_response)

    receipt = execute_provider_capture_acceptance(
        fetch_raw_response=fetch,
        request=request,
        provider="massive",
        source_symbol="AAPL",
        retrieval_date=retrieval_date,
        security=_security(),
        session_date=session_date,
        expected_session_start_utc=start,
        expected_session_end_utc_exclusive=start + timedelta(minutes=2),
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert fetch.calls == [("massive", request)]
    assert receipt["request"] == request
    assert receipt["raw_artifact_sha256"] == hashlib.sha256(raw_response).hexdigest()
    assert receipt["observed_minute_count"] == 2

    failing = _FakeFetchProviderRawResponse(error=RuntimeError("fetch_failed"))
    with raises(RuntimeError, match="fetch_failed"):
        execute_provider_capture_acceptance(
            fetch_raw_response=failing,
            request=request,
            provider="massive",
            source_symbol="AAPL",
            retrieval_date=retrieval_date,
            security=_security(),
            session_date=session_date,
            expected_session_start_utc=start,
            expected_session_end_utc_exclusive=start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )
    assert failing.calls == [("massive", request)]
