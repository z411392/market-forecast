from datetime import date, datetime, timezone

from pytest import mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.decode_massive_minute_aggregates import (
    decode_massive_minute_aggregates,
)


def _security(timezone_name: str = "America/New_York") -> SecurityIdentity:
    return {
        "symbol": "AAPL",
        "exchange": "XNAS",
        "timezone": timezone_name,
        "calendar_id": "XNAS",
    }


def _timestamp_ms(minute: int) -> int:
    instant = datetime(2025, 11, 26, 14, 30 + minute, tzinfo=timezone.utc)
    return int(instant.timestamp() * 1000)


def _result(minute: int) -> dict[str, object]:
    return {
        "o": 100.0 + minute,
        "h": 101.0 + minute,
        "l": 99.0 + minute,
        "c": 100.5 + minute,
        "v": 1000.0 + minute,
        "t": _timestamp_ms(minute),
    }


def _payload(adjusted: bool = False) -> dict[str, object]:
    return {
        "ticker": "AAPL",
        "adjusted": adjusted,
        "status": "OK",
        "results": [_result(0), _result(2)],
    }


@mark.unit
def test_decode_massive_minute_aggregates() -> None:
    bars = decode_massive_minute_aggregates(
        payload=_payload(adjusted=False),
        expected_source_symbol="AAPL",
        security=_security(),
    )

    assert len(bars) == 2
    assert bars[0]["bar_start_utc"] == datetime(
        2025,
        11,
        26,
        14,
        30,
        tzinfo=timezone.utc,
    )
    assert bars[0]["session_date"] == date(2025, 11, 26)
    assert bars[0]["open"] == 100.0
    assert bars[0]["high"] == 101.0
    assert bars[0]["low"] == 99.0
    assert bars[0]["close"] == 100.5
    assert bars[0]["volume"] == 1000.0
    assert bars[0]["price_basis"] == "as_printed"
    assert bars[1]["bar_start_utc"] == datetime(
        2025,
        11,
        26,
        14,
        32,
        tzinfo=timezone.utc,
    )

    adjusted = decode_massive_minute_aggregates(
        payload=_payload(adjusted=True),
        expected_source_symbol="AAPL",
        security=_security(),
    )
    assert all(bar["price_basis"] == "split_adjusted" for bar in adjusted)

    bad_status = {**_payload(), "status": "ERROR"}
    with raises(InvalidProviderCaptureInputError, match="massive_status_not_ok"):
        decode_massive_minute_aggregates(bad_status, "AAPL", _security())

    wrong_ticker = {**_payload(), "ticker": "MSFT"}
    with raises(InvalidProviderCaptureInputError, match="massive_ticker_mismatch"):
        decode_massive_minute_aggregates(wrong_ticker, "AAPL", _security())

    invalid_adjusted = {**_payload(), "adjusted": "false"}
    with raises(InvalidProviderCaptureInputError, match="massive_adjusted_not_boolean"):
        decode_massive_minute_aggregates(invalid_adjusted, "AAPL", _security())

    with raises(InvalidProviderCaptureInputError, match="massive_results_missing"):
        decode_massive_minute_aggregates(
            {"ticker": "AAPL", "adjusted": False, "status": "OK"},
            "AAPL",
            _security(),
        )

    empty_results = {**_payload(), "results": []}
    with raises(InvalidProviderCaptureInputError, match="massive_results_empty"):
        decode_massive_minute_aggregates(empty_results, "AAPL", _security())

    malformed = {**_payload(), "results": [{"o": 100.0}]}
    with raises(InvalidProviderCaptureInputError, match="massive_result_missing_field"):
        decode_massive_minute_aggregates(malformed, "AAPL", _security())

    non_finite = _result(0)
    non_finite["c"] = float("nan")
    with raises(InvalidProviderCaptureInputError, match="massive_invalid_price"):
        decode_massive_minute_aggregates(
            {**_payload(), "results": [non_finite]},
            "AAPL",
            _security(),
        )

    zero_price = _result(0)
    zero_price["o"] = 0.0
    with raises(InvalidProviderCaptureInputError, match="massive_invalid_price"):
        decode_massive_minute_aggregates(
            {**_payload(), "results": [zero_price]},
            "AAPL",
            _security(),
        )

    negative_volume = _result(0)
    negative_volume["v"] = -1.0
    with raises(InvalidProviderCaptureInputError, match="massive_invalid_volume"):
        decode_massive_minute_aggregates(
            {**_payload(), "results": [negative_volume]},
            "AAPL",
            _security(),
        )

    invalid_envelope = _result(0)
    invalid_envelope["h"] = 100.25
    with raises(InvalidProviderCaptureInputError, match="massive_invalid_ohlc_envelope"):
        decode_massive_minute_aggregates(
            {**_payload(), "results": [invalid_envelope]},
            "AAPL",
            _security(),
        )

    float_timestamp = _result(0)
    float_timestamp["t"] = float(_timestamp_ms(0))
    with raises(InvalidProviderCaptureInputError, match="massive_invalid_timestamp"):
        decode_massive_minute_aggregates(
            {**_payload(), "results": [float_timestamp]},
            "AAPL",
            _security(),
        )

    descending = {**_payload(), "results": [_result(2), _result(0)]}
    with raises(InvalidProviderCaptureInputError, match="massive_non_increasing_timestamps"):
        decode_massive_minute_aggregates(descending, "AAPL", _security())

    with raises(InvalidProviderCaptureInputError, match="massive_invalid_timezone"):
        decode_massive_minute_aggregates(
            _payload(),
            "AAPL",
            _security("Invalid/Timezone"),
        )
