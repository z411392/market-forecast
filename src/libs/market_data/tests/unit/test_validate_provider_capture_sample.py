from datetime import date, datetime, timedelta, timezone

from pytest import mark, raises

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.provider_capture_manifest import ProviderCaptureManifest
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.validate_provider_capture_sample import (
    validate_provider_capture_sample,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "TEST",
        "exchange": "XNYS",
        "timezone": "America/New_York",
        "calendar_id": "XNYS",
    }


def _bar(index: int, start: datetime) -> CanonicalMinuteBar:
    price = 100.0 + index
    return {
        "security": _security(),
        "bar_start_utc": start + timedelta(minutes=index),
        "session_date": date(2026, 9, 25),
        "open": price,
        "high": price + 0.5,
        "low": price - 0.5,
        "close": price + 0.25,
        "volume": 1000.0 + index,
        "price_basis": "as_printed",
    }


def _manifest(start: datetime, count: int = 3) -> ProviderCaptureManifest:
    return {
        "provider": "massive",
        "source_symbol": "TEST",
        "retrieval_date": date(2026, 9, 28),
        "security": _security(),
        "session_date": date(2026, 9, 25),
        "expected_session_start_utc": start,
        "expected_session_end_utc_exclusive": start + timedelta(minutes=3),
        "expected_minute_count": count,
        "price_basis": "as_printed",
        "raw_artifact_sha256": "a" * 64,
    }


@mark.unit
def test_validate_provider_capture_sample() -> None:
    start = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)
    bars = tuple(_bar(index, start) for index in range(3))
    manifest = _manifest(start)

    assert validate_provider_capture_sample(manifest, bars) is bars

    with raises(InvalidProviderCaptureInputError, match="empty_bars"):
        validate_provider_capture_sample(manifest, ())

    with raises(InvalidProviderCaptureInputError, match="unexpected_minute_count"):
        validate_provider_capture_sample(_manifest(start, count=4), bars)

    mixed_basis = list(bars)
    mixed_basis[1] = {**mixed_basis[1], "price_basis": "split_adjusted"}
    with raises(InvalidProviderCaptureInputError, match="mixed_price_basis"):
        validate_provider_capture_sample(manifest, tuple(mixed_basis))

    wrong_session = list(bars)
    wrong_session[1] = {**wrong_session[1], "session_date": date(2026, 9, 26)}
    with raises(InvalidProviderCaptureInputError, match="session_date_mismatch"):
        validate_provider_capture_sample(manifest, tuple(wrong_session))

    other_security = {
        "symbol": "OTHER",
        "exchange": "XNYS",
        "timezone": "America/New_York",
        "calendar_id": "XNYS",
    }
    mixed_security = list(bars)
    mixed_security[1] = {**mixed_security[1], "security": other_security}
    with raises(InvalidProviderCaptureInputError, match="mixed_security"):
        validate_provider_capture_sample(manifest, tuple(mixed_security))

    outside = list(bars)
    outside[2] = {
        **outside[2],
        "bar_start_utc": manifest["expected_session_end_utc_exclusive"],
    }
    with raises(InvalidProviderCaptureInputError, match="bar_outside_session"):
        validate_provider_capture_sample(manifest, tuple(outside))

    naive_time = list(bars)
    naive_time[1] = {
        **naive_time[1],
        "bar_start_utc": naive_time[1]["bar_start_utc"].replace(tzinfo=None),
    }
    with raises(InvalidProviderCaptureInputError, match="bar_start_not_utc"):
        validate_provider_capture_sample(manifest, tuple(naive_time))

    duplicate = list(bars)
    duplicate[2] = {**duplicate[2], "bar_start_utc": duplicate[1]["bar_start_utc"]}
    with raises(InvalidProviderCaptureInputError, match="non_increasing_bar_starts"):
        validate_provider_capture_sample(manifest, tuple(duplicate))

    bad_start = {**manifest, "expected_session_start_utc": start.replace(tzinfo=None)}
    with raises(InvalidProviderCaptureInputError, match="session_start_not_utc"):
        validate_provider_capture_sample(bad_start, bars)

    bad_end = {
        **manifest,
        "expected_session_end_utc_exclusive": start - timedelta(minutes=1),
    }
    with raises(InvalidProviderCaptureInputError, match="invalid_session_window"):
        validate_provider_capture_sample(bad_end, bars)

    bad_hash = {**manifest, "raw_artifact_sha256": "not-a-sha"}
    with raises(InvalidProviderCaptureInputError, match="invalid_artifact_sha256"):
        validate_provider_capture_sample(bad_hash, bars)
