from datetime import date, datetime, timezone

from pytest import mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.decode_finmind_stock_kbar import decode_finmind_stock_kbar


def _security(timezone_name: str = "Asia/Taipei") -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": timezone_name,
        "calendar_id": "XTAI",
    }


def _row(minute: str = "09:00:00") -> dict[str, object]:
    return {
        "date": "2025-11-26",
        "minute": minute,
        "stock_id": "2330",
        "open": 1000.0,
        "high": 1005.0,
        "low": 995.0,
        "close": 1002.0,
        "volume": 1234.0,
    }


def _payload() -> dict[str, object]:
    return {
        "msg": "success",
        "status": 200,
        "data": [_row("09:00:00"), _row("09:02:00")],
    }


@mark.unit
def test_decode_finmind_stock_kbar() -> None:
    bars = decode_finmind_stock_kbar(
        payload=_payload(),
        expected_source_symbol="2330",
        security=_security(),
    )

    assert len(bars) == 2
    assert bars[0]["bar_start_utc"] == datetime(
        2025,
        11,
        26,
        1,
        0,
        tzinfo=timezone.utc,
    )
    assert bars[0]["session_date"] == date(2025, 11, 26)
    assert bars[0]["open"] == 1000.0
    assert bars[0]["high"] == 1005.0
    assert bars[0]["low"] == 995.0
    assert bars[0]["close"] == 1002.0
    assert bars[0]["volume"] == 1234.0
    assert bars[0]["price_basis"] == "as_printed"
    assert bars[1]["bar_start_utc"] == datetime(
        2025,
        11,
        26,
        1,
        2,
        tzinfo=timezone.utc,
    )

    bad_status = {**_payload(), "status": 402}
    with raises(InvalidProviderCaptureInputError, match="finmind_status_not_ok"):
        decode_finmind_stock_kbar(bad_status, "2330", _security())

    boolean_status = {**_payload(), "status": True}
    with raises(InvalidProviderCaptureInputError, match="finmind_status_not_ok"):
        decode_finmind_stock_kbar(boolean_status, "2330", _security())

    with raises(InvalidProviderCaptureInputError, match="finmind_data_missing"):
        decode_finmind_stock_kbar(
            {"msg": "success", "status": 200},
            "2330",
            _security(),
        )

    non_list_data = {**_payload(), "data": "not-a-list"}
    with raises(InvalidProviderCaptureInputError, match="finmind_data_missing"):
        decode_finmind_stock_kbar(non_list_data, "2330", _security())

    empty_data = {**_payload(), "data": []}
    with raises(InvalidProviderCaptureInputError, match="finmind_data_empty"):
        decode_finmind_stock_kbar(empty_data, "2330", _security())

    malformed = {**_payload(), "data": [{"date": "2025-11-26"}]}
    with raises(InvalidProviderCaptureInputError, match="finmind_row_missing_field"):
        decode_finmind_stock_kbar(malformed, "2330", _security())

    wrong_symbol = _row()
    wrong_symbol["stock_id"] = "2317"
    with raises(InvalidProviderCaptureInputError, match="finmind_stock_id_mismatch"):
        decode_finmind_stock_kbar(
            {**_payload(), "data": [wrong_symbol]},
            "2330",
            _security(),
        )

    bad_date = _row()
    bad_date["date"] = "2025/11/26"
    with raises(InvalidProviderCaptureInputError, match="finmind_invalid_local_timestamp"):
        decode_finmind_stock_kbar(
            {**_payload(), "data": [bad_date]},
            "2330",
            _security(),
        )

    bad_minute = _row()
    bad_minute["minute"] = "9:00"
    with raises(InvalidProviderCaptureInputError, match="finmind_invalid_local_timestamp"):
        decode_finmind_stock_kbar(
            {**_payload(), "data": [bad_minute]},
            "2330",
            _security(),
        )

    non_finite = _row()
    non_finite["close"] = float("nan")
    with raises(InvalidProviderCaptureInputError, match="finmind_invalid_price"):
        decode_finmind_stock_kbar(
            {**_payload(), "data": [non_finite]},
            "2330",
            _security(),
        )

    zero_price = _row()
    zero_price["open"] = 0.0
    with raises(InvalidProviderCaptureInputError, match="finmind_invalid_price"):
        decode_finmind_stock_kbar(
            {**_payload(), "data": [zero_price]},
            "2330",
            _security(),
        )

    negative_volume = _row()
    negative_volume["volume"] = -1.0
    with raises(InvalidProviderCaptureInputError, match="finmind_invalid_volume"):
        decode_finmind_stock_kbar(
            {**_payload(), "data": [negative_volume]},
            "2330",
            _security(),
        )

    bad_envelope = _row()
    bad_envelope["high"] = 1001.0
    with raises(InvalidProviderCaptureInputError, match="finmind_invalid_ohlc_envelope"):
        decode_finmind_stock_kbar(
            {**_payload(), "data": [bad_envelope]},
            "2330",
            _security(),
        )

    duplicate = {**_payload(), "data": [_row("09:00:00"), _row("09:00:00")]}
    with raises(InvalidProviderCaptureInputError, match="finmind_non_increasing_timestamps"):
        decode_finmind_stock_kbar(duplicate, "2330", _security())

    descending = {**_payload(), "data": [_row("09:02:00"), _row("09:00:00")]}
    with raises(InvalidProviderCaptureInputError, match="finmind_non_increasing_timestamps"):
        decode_finmind_stock_kbar(descending, "2330", _security())

    with raises(InvalidProviderCaptureInputError, match="finmind_invalid_timezone"):
        decode_finmind_stock_kbar(
            _payload(),
            "2330",
            _security("Invalid/Timezone"),
        )
