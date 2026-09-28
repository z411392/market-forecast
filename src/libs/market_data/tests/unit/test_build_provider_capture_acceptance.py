import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from pytest import mark, raises

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_finmind_stock_kbar_request import (
    build_finmind_stock_kbar_request,
)
from libs.market_data.services.build_massive_minute_request import (
    build_massive_minute_request,
)
from libs.market_data.services.build_provider_capture_acceptance import (
    build_provider_capture_acceptance,
)


def _us_security() -> SecurityIdentity:
    return {
        "symbol": "AAPL",
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _tw_security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _massive_raw() -> bytes:
    start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    results = []
    for index in range(2):
        results.append(
            {
                "o": 100.0 + index,
                "h": 101.0 + index,
                "l": 99.0 + index,
                "c": 100.5 + index,
                "v": 1000.0 + index,
                "t": int((start + timedelta(minutes=index)).timestamp() * 1000),
            }
        )
    return json.dumps(
        {
            "ticker": "AAPL",
            "adjusted": False,
            "status": "OK",
            "results": results,
        },
        separators=(",", ":"),
    ).encode()


def _finmind_raw() -> bytes:
    return json.dumps(
        {
            "msg": "success",
            "status": 200,
            "data": [
                {
                    "date": "2025-11-26",
                    "minute": minute,
                    "stock_id": "2330",
                    "open": 1000.0,
                    "high": 1005.0,
                    "low": 995.0,
                    "close": 1002.0,
                    "volume": 1234.0,
                }
                for minute in ("09:00:00", "09:01:00")
            ],
        },
        separators=(",", ":"),
    ).encode()


@mark.unit
def test_build_provider_capture_acceptance() -> None:
    retrieval_date = date(2026, 9, 28)

    us_raw = _massive_raw()
    us_start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    us_request = build_massive_minute_request("AAPL", date(2025, 11, 26))
    us_receipt = build_provider_capture_acceptance(
        request=us_request,
        provider="massive",
        raw_response=us_raw,
        source_symbol="AAPL",
        retrieval_date=retrieval_date,
        security=_us_security(),
        session_date=date(2025, 11, 26),
        expected_session_start_utc=us_start,
        expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert us_receipt["provider"] == "massive"
    assert us_receipt["raw_artifact_sha256"] == hashlib.sha256(us_raw).hexdigest()
    assert us_receipt["request"] == us_request
    assert us_receipt["observed_minute_count"] == 2
    assert us_receipt["gap_count"] == 0
    assert us_receipt["missing_grid_minutes"] == 0

    tw_raw = _finmind_raw()
    tw_start = datetime(2025, 11, 26, 1, 0, tzinfo=timezone.utc)
    tw_request = build_finmind_stock_kbar_request("2330", date(2025, 11, 26))
    tw_receipt = build_provider_capture_acceptance(
        request=tw_request,
        provider="finmind",
        raw_response=tw_raw,
        source_symbol="2330",
        retrieval_date=retrieval_date,
        security=_tw_security(),
        session_date=date(2025, 11, 26),
        expected_session_start_utc=tw_start,
        expected_session_end_utc_exclusive=tw_start + timedelta(minutes=2),
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert tw_receipt["provider"] == "finmind"
    assert tw_receipt["raw_artifact_sha256"] == hashlib.sha256(tw_raw).hexdigest()
    assert tw_receipt["request"] == tw_request
    assert tw_receipt["observed_minute_count"] == 2

    bad_request: ProviderRequestSpec = {
        **us_request,
        "query": us_request["query"] + (("adjusted", "true"),),
    }
    with raises(InvalidProviderCaptureInputError, match="request_spec_mismatch"):
        build_provider_capture_acceptance(
            request=bad_request,
            provider="massive",
            raw_response=us_raw,
            source_symbol="AAPL",
            retrieval_date=retrieval_date,
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )
