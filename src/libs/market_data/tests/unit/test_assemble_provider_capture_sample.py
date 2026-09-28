import hashlib
import json
from datetime import date, datetime, timezone

from pytest import mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.assemble_provider_capture_sample import (
    assemble_provider_capture_sample,
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


def _massive_raw(adjusted: bool = False) -> bytes:
    payload = {
        "ticker": "AAPL",
        "adjusted": adjusted,
        "status": "OK",
        "results": [
            {
                "o": 100.0,
                "h": 101.0,
                "l": 99.0,
                "c": 100.5,
                "v": 1000.0,
                "t": 1764167400000,
            },
            {
                "o": 101.0,
                "h": 102.0,
                "l": 100.0,
                "c": 101.5,
                "v": 1001.0,
                "t": 1764167520000,
            },
        ],
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _finmind_raw() -> bytes:
    payload = {
        "msg": "success",
        "status": 200,
        "data": [
            {
                "date": "2025-11-26",
                "minute": "09:00:00",
                "stock_id": "2330",
                "open": 1000.0,
                "high": 1005.0,
                "low": 995.0,
                "close": 1002.0,
                "volume": 1234.0,
            },
            {
                "date": "2025-11-26",
                "minute": "09:02:00",
                "stock_id": "2330",
                "open": 1001.0,
                "high": 1006.0,
                "low": 996.0,
                "close": 1003.0,
                "volume": 1235.0,
            },
        ],
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


@mark.unit
def test_assemble_provider_capture_sample() -> None:
    us_start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    us_end = datetime(2025, 11, 26, 14, 33, tzinfo=timezone.utc)
    massive_raw = _massive_raw()

    manifest, bars = assemble_provider_capture_sample(
        provider="massive",
        raw_response=massive_raw,
        source_symbol="AAPL",
        retrieval_date=date(2026, 9, 28),
        security=_us_security(),
        session_date=date(2025, 11, 26),
        expected_session_start_utc=us_start,
        expected_session_end_utc_exclusive=us_end,
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert manifest["provider"] == "massive"
    assert manifest["source_symbol"] == "AAPL"
    assert manifest["raw_artifact_sha256"] == hashlib.sha256(massive_raw).hexdigest()
    assert manifest["price_basis"] == "as_printed"
    assert bars[0]["bar_start_utc"] == us_start
    assert bars[1]["bar_start_utc"] == datetime(
        2025,
        11,
        26,
        14,
        32,
        tzinfo=timezone.utc,
    )

    tw_start = datetime(2025, 11, 26, 1, 0, tzinfo=timezone.utc)
    tw_end = datetime(2025, 11, 26, 1, 3, tzinfo=timezone.utc)
    finmind_raw = _finmind_raw()

    tw_manifest, tw_bars = assemble_provider_capture_sample(
        provider="finmind",
        raw_response=finmind_raw,
        source_symbol="2330",
        retrieval_date=date(2026, 9, 28),
        security=_tw_security(),
        session_date=date(2025, 11, 26),
        expected_session_start_utc=tw_start,
        expected_session_end_utc_exclusive=tw_end,
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert tw_manifest["provider"] == "finmind"
    assert tw_manifest["raw_artifact_sha256"] == hashlib.sha256(finmind_raw).hexdigest()
    assert tw_bars[0]["bar_start_utc"] == tw_start
    assert tw_bars[1]["bar_start_utc"] == datetime(
        2025,
        11,
        26,
        1,
        2,
        tzinfo=timezone.utc,
    )

    with raises(InvalidProviderCaptureInputError, match="mixed_price_basis"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=_massive_raw(adjusted=True),
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_end,
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="unsupported_provider"):
        assemble_provider_capture_sample(
            provider="other",
            raw_response=massive_raw,
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_end,
            expected_minute_count=2,
            price_basis="as_printed",
        )

    bad_raw_inputs = (
        ("not-bytes", "raw_response_not_bytes"),
        (b"", "raw_response_empty"),
        (b"{not-json}", "raw_response_invalid_json"),
        (b"[]", "raw_response_not_object"),
    )
    for raw_response, error in bad_raw_inputs:
        with raises(InvalidProviderCaptureInputError, match=error):
            assemble_provider_capture_sample(
                provider="massive",
                raw_response=raw_response,
                source_symbol="AAPL",
                retrieval_date=date(2026, 9, 28),
                security=_us_security(),
                session_date=date(2025, 11, 26),
                expected_session_start_utc=us_start,
                expected_session_end_utc_exclusive=us_end,
                expected_minute_count=2,
                price_basis="as_printed",
            )

    with raises(InvalidProviderCaptureInputError, match="retrieval_date_not_plain_date"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=massive_raw,
            source_symbol="AAPL",
            retrieval_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_end,
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="session_date_not_plain_date"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=massive_raw,
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=datetime(2025, 11, 26, tzinfo=timezone.utc),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_end,
            expected_minute_count=2,
            price_basis="as_printed",
        )
