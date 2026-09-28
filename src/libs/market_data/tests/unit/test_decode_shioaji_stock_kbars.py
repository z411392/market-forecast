from datetime import date, datetime, timezone

from pytest import approx, mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.decode_shioaji_stock_kbars import decode_shioaji_stock_kbars


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _provider_ns(hour: int, minute: int) -> int:
    value = datetime(2026, 9, 24, hour, minute, tzinfo=timezone.utc)
    return int(value.timestamp() * 1_000_000_000)


def _payload() -> dict[str, object]:
    labels = [
        *[
            _provider_ns(9 + minute_index // 60, 1 + minute_index % 60)
            for minute_index in range(59)
        ],
        *[
            _provider_ns(10 + minute_index // 60, minute_index % 60)
            for minute_index in range(60)
        ],
        *[
            _provider_ns(11 + minute_index // 60, minute_index % 60)
            for minute_index in range(60)
        ],
        *[
            _provider_ns(12 + minute_index // 60, minute_index % 60)
            for minute_index in range(60)
        ],
        *[_provider_ns(13, minute_index) for minute_index in range(25)],
        _provider_ns(13, 30),
    ]
    count = len(labels)
    opens = [100.0 + index * 0.01 for index in range(count)]
    closes = [value + 0.005 for value in opens]
    return {
        "ts": labels,
        "Open": opens,
        "High": [value + 0.02 for value in closes],
        "Low": [value - 0.02 for value in opens],
        "Close": closes,
        "Volume": [100 + index for index in range(count)],
        "Amount": [100_000.0 + index for index in range(count)],
    }


@mark.unit
def test_decode_shioaji_stock_kbars() -> None:
    bars, closing = decode_shioaji_stock_kbars(
        _payload(),
        _security(),
        date(2026, 9, 24),
        "as_printed",
    )

    assert len(bars) == 265
    assert bars[0]["bar_start_utc"] == datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
    assert bars[-1]["bar_start_utc"] == datetime(2026, 9, 24, 5, 24, tzinfo=timezone.utc)
    assert bars[0]["session_date"] == date(2026, 9, 24)
    assert bars[0]["price_basis"] == "as_printed"

    payload = _payload()
    assert closing["security"] == _security()
    assert closing["session_date"] == date(2026, 9, 24)
    assert closing["matched_at_utc"] == datetime(2026, 9, 24, 5, 30, tzinfo=timezone.utc)
    assert closing["price"] == approx(payload["Close"][-1])
    assert closing["volume"] == approx(payload["Volume"][-1])
    assert closing["price_basis"] == "as_printed"

    missing_close = _payload()
    for key in ("ts", "Open", "High", "Low", "Close", "Volume", "Amount"):
        missing_close[key] = missing_close[key][:-1]
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_stock_kbars(
            missing_close,
            _security(),
            date(2026, 9, 24),
            "as_printed",
        )

    wrong_session = _payload()
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_stock_kbars(
            wrong_session,
            _security(),
            date(2026, 9, 23),
            "as_printed",
        )
