from datetime import date, datetime, timedelta, timezone

from pytest import mark, raises

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.provider_capture_manifest import ProviderCaptureManifest
from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_provider_capture_acceptance_receipt import (
    build_provider_capture_acceptance_receipt,
)
from libs.market_data.services.build_massive_minute_request import (
    build_massive_minute_request,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "AAPL",
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _manifest(start: datetime) -> ProviderCaptureManifest:
    return {
        "provider": "massive",
        "source_symbol": "AAPL",
        "retrieval_date": date(2026, 9, 28),
        "security": _security(),
        "session_date": date(2025, 11, 26),
        "expected_session_start_utc": start,
        "expected_session_end_utc_exclusive": start + timedelta(minutes=4),
        "expected_minute_count": 3,
        "price_basis": "as_printed",
        "raw_artifact_sha256": "a" * 64,
    }


def _bar(start: datetime, minute_offset: int) -> CanonicalMinuteBar:
    return {
        "security": _security(),
        "bar_start_utc": start + timedelta(minutes=minute_offset),
        "session_date": date(2025, 11, 26),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0,
        "price_basis": "as_printed",
    }


@mark.unit
def test_build_provider_capture_acceptance_receipt() -> None:
    start = datetime(2025, 11, 26, 14, 30, tzinfo=timezone.utc)
    manifest = _manifest(start)
    bars = (
        _bar(start, 0),
        _bar(start, 1),
        _bar(start, 3),
    )
    request = build_massive_minute_request("AAPL", date(2025, 11, 26))

    receipt = build_provider_capture_acceptance_receipt(
        request=request,
        manifest=manifest,
        bars=bars,
    )

    assert receipt == {
        "provider": "massive",
        "source_symbol": "AAPL",
        "security": _security(),
        "session_date": date(2025, 11, 26),
        "retrieval_date": date(2026, 9, 28),
        "request": request,
        "price_basis": "as_printed",
        "raw_artifact_sha256": "a" * 64,
        "expected_minute_count": 3,
        "observed_minute_count": 3,
        "first_bar_start_utc": start,
        "last_bar_start_utc": start + timedelta(minutes=3),
        "gap_count": 1,
        "missing_grid_minutes": 1,
    }

    bad_request: ProviderRequestSpec = {
        **request,
        "query": request["query"] + (("adjusted", "true"),),
    }
    with raises(InvalidProviderCaptureInputError, match="request_spec_mismatch"):
        build_provider_capture_acceptance_receipt(
            request=bad_request,
            manifest=manifest,
            bars=bars,
        )

    bad_manifest = {**manifest, "expected_minute_count": 4}
    with raises(InvalidProviderCaptureInputError, match="unexpected_minute_count"):
        build_provider_capture_acceptance_receipt(
            request=request,
            manifest=bad_manifest,
            bars=bars,
        )
