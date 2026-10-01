from datetime import date, datetime, timezone

from pytest import mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.decode_alpaca_stock_bars import (
    decode_alpaca_stock_bars,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "AAPL",
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _payload() -> dict[str, object]:
    return {
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
                "n": 11429,
                "vw": 216.064963,
            },
            {
                "t": "2024-07-02T13:31:00Z",
                "o": 215.93,
                "h": 216.08,
                "l": 215.72,
                "c": 215.91,
                "v": 220000,
                "n": 5000,
                "vw": 215.90,
            },
        ],
    }


@mark.unit
def test_decode_alpaca_stock_bars() -> None:
    bars = decode_alpaca_stock_bars(
        payload=_payload(),
        expected_source_symbol="AAPL",
        security=_security(),
        price_basis="as_printed",
    )

    assert len(bars) == 2
    assert bars[0]["security"] == _security()
    assert bars[0]["session_date"] == date(2024, 7, 2)
    assert bars[0]["bar_start_utc"] == datetime(
        2024, 7, 2, 13, 30, tzinfo=timezone.utc
    )
    assert bars[0]["price_basis"] == "as_printed"
    assert bars[0]["open"] == 216.15
    assert bars[0]["close"] == 215.9301
    assert bars[0]["volume"] == 1171698.0

    split = decode_alpaca_stock_bars(
        payload=_payload(),
        expected_source_symbol="AAPL",
        security=_security(),
        price_basis="split_adjusted",
    )
    assert split[0]["price_basis"] == "split_adjusted"

    bad_symbol = {**_payload(), "symbol": "MSFT"}
    with raises(InvalidProviderCaptureInputError):
        decode_alpaca_stock_bars(
            payload=bad_symbol,
            expected_source_symbol="AAPL",
            security=_security(),
            price_basis="as_printed",
        )

    paged = {**_payload(), "next_page_token": "next"}
    with raises(InvalidProviderCaptureInputError):
        decode_alpaca_stock_bars(
            payload=paged,
            expected_source_symbol="AAPL",
            security=_security(),
            price_basis="as_printed",
        )

    descending = _payload()
    descending["bars"] = list(reversed(descending["bars"]))  # type: ignore[index]
    with raises(InvalidProviderCaptureInputError):
        decode_alpaca_stock_bars(
            payload=descending,
            expected_source_symbol="AAPL",
            security=_security(),
            price_basis="as_printed",
        )
