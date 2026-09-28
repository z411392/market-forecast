import hashlib
import json
from datetime import date, datetime, timedelta, timezone

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
    start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    rows = []
    for index in range(2):
        rows.append(
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
            "adjusted": adjusted,
            "status": "OK",
            "results": rows,
        },
        separators=(",", ":"),
    ).encode()


def _finmind_raw() -> bytes:
    rows = []
    for minute in ("09:00:00", "09:01:00"):
        rows.append(
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
        )
    return json.dumps(
        {
            "msg": "success",
            "status": 200,
            "data": rows,
        },
        separators=(",", ":"),
    ).encode()


@mark.unit
def test_assemble_provider_capture_sample() -> None:
    us_raw = _massive_raw()
    us_start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)

    us_manifest, us_bars = assemble_provider_capture_sample(
        provider="massive",
        raw_response=us_raw,
        source_symbol="AAPL",
        retrieval_date=date(2026, 9, 28),
        security=_us_security(),
        session_date=date(2025, 11, 26),
        expected_session_start_utc=us_start,
        expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert us_manifest["raw_artifact_sha256"] == hashlib.sha256(us_raw).hexdigest()
    assert us_manifest["provider"] == "massive"
    assert us_manifest["source_symbol"] == "AAPL"
    assert us_bars[0]["bar_start_utc"] == us_start
    assert len(us_bars) == 2

    tw_raw = _finmind_raw()
    tw_start = datetime(2025, 11, 26, 1, 0, tzinfo=timezone.utc)
    tw_manifest, tw_bars = assemble_provider_capture_sample(
        provider="finmind",
        raw_response=tw_raw,
        source_symbol="2330",
        retrieval_date=date(2026, 9, 28),
        security=_tw_security(),
        session_date=date(2025, 11, 26),
        expected_session_start_utc=tw_start,
        expected_session_end_utc_exclusive=tw_start + timedelta(minutes=2),
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert tw_manifest["raw_artifact_sha256"] == hashlib.sha256(tw_raw).hexdigest()
    assert tw_manifest["provider"] == "finmind"
    assert tw_manifest["source_symbol"] == "2330"
    assert tw_bars[0]["bar_start_utc"] == tw_start
    assert len(tw_bars) == 2

    for invalid_raw in ("{}", bytearray(b"{}")):
        with raises(InvalidProviderCaptureInputError, match="raw_response_not_bytes"):
            assemble_provider_capture_sample(
                provider="massive",
                raw_response=invalid_raw,
                source_symbol="AAPL",
                retrieval_date=date(2026, 9, 28),
                security=_us_security(),
                session_date=date(2025, 11, 26),
                expected_session_start_utc=us_start,
                expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
                expected_minute_count=2,
                price_basis="as_printed",
            )

    with raises(InvalidProviderCaptureInputError, match="raw_response_empty"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=b"",
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="raw_response_invalid_json"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=b"{",
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="raw_response_invalid_json"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=b'{"value":NaN}',
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="raw_response_not_object"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=b"[]",
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="unsupported_provider"):
        assemble_provider_capture_sample(
            provider="other",
            raw_response=b"{}",
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="retrieval_date_not_plain_date"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=us_raw,
            source_symbol="AAPL",
            retrieval_date=datetime(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="session_date_not_plain_date"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=us_raw,
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=datetime(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="mixed_price_basis"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=us_raw,
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=2,
            price_basis="split_adjusted",
        )

    with raises(InvalidProviderCaptureInputError, match="unexpected_minute_count"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=us_raw,
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start + timedelta(minutes=2),
            expected_minute_count=3,
            price_basis="as_printed",
        )

    with raises(InvalidProviderCaptureInputError, match="invalid_session_window"):
        assemble_provider_capture_sample(
            provider="massive",
            raw_response=us_raw,
            source_symbol="AAPL",
            retrieval_date=date(2026, 9, 28),
            security=_us_security(),
            session_date=date(2025, 11, 26),
            expected_session_start_utc=us_start,
            expected_session_end_utc_exclusive=us_start,
            expected_minute_count=2,
            price_basis="as_printed",
        )
