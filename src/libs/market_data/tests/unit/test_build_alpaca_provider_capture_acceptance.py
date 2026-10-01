import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from pytest import mark

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.build_alpaca_historical_bars_request import (
    build_alpaca_historical_bars_request,
)
from libs.market_data.services.build_provider_capture_acceptance import (
    build_provider_capture_acceptance,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "AAPL",
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


@mark.unit
def test_build_alpaca_provider_capture_acceptance() -> None:
    start = datetime(2024, 7, 2, 13, 30, tzinfo=timezone.utc)
    end = start + timedelta(minutes=2)
    raw = json.dumps(
        {
            "symbol": "AAPL",
            "next_page_token": None,
            "bars": [
                {
                    "t": "2024-07-02T13:30:00Z",
                    "o": 216.15,
                    "h": 216.47,
                    "l": 215.84,
                    "c": 215.9301,
                    "v": 1171698,
                },
                {
                    "t": "2024-07-02T13:31:00Z",
                    "o": 215.93,
                    "h": 216.08,
                    "l": 215.72,
                    "c": 215.91,
                    "v": 220000,
                },
            ],
        },
        separators=(",", ":"),
    ).encode()
    request = build_alpaca_historical_bars_request(
        source_symbol="AAPL",
        session_start_utc=start,
        session_end_utc_exclusive=end,
        price_basis="as_printed",
    )

    receipt = build_provider_capture_acceptance(
        request=request,
        provider="alpaca",
        raw_response=raw,
        source_symbol="AAPL",
        retrieval_date=date(2026, 10, 1),
        security=_security(),
        session_date=date(2024, 7, 2),
        expected_session_start_utc=start,
        expected_session_end_utc_exclusive=end,
        expected_minute_count=2,
        price_basis="as_printed",
    )

    assert receipt["provider"] == "alpaca"
    assert receipt["request"] == request
    assert receipt["raw_artifact_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["observed_minute_count"] == 2
    assert receipt["gap_count"] == 0
    assert receipt["missing_grid_minutes"] == 0
