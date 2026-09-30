import json
from copy import deepcopy
from datetime import date, datetime, time, timezone

from pytest import mark, raises

from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.decode_shioaji_historical_ticks import (
    decode_shioaji_historical_ticks,
)


def _request() -> HistoricalTickRequestSpec:
    return {
        "provider": "shioaji",
        "source_symbol": "2330",
        "session_date": date(2026, 9, 24),
        "query_type": "RangeTime",
        "time_start_local": time(9, 0),
        "time_end_local": time(13, 30, 59),
    }


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _provider_ns(
    hour: int,
    minute: int,
    second: int,
    microsecond: int = 0,
) -> int:
    wall_clock = datetime(
        2026,
        9,
        24,
        hour,
        minute,
        second,
        tzinfo=timezone.utc,
    )
    return int(wall_clock.timestamp()) * 1_000_000_000 + microsecond * 1_000


def _payload() -> dict[str, object]:
    timestamps = [
        _provider_ns(9, 0, 3, 123456),
        _provider_ns(9, 0, 3, 123456),
        _provider_ns(13, 30, 0),
    ]
    return {
        "ts": timestamps,
        "close": [2480.0, 2480.5, 2475.0],
        "volume": [1000, 2000, 3000],
        "bid_price": [2475.0, 2480.0, 2470.0],
        "bid_volume": [10, 20, 30],
        "ask_price": [2480.0, 2480.5, 2475.0],
        "ask_volume": [11, 21, 31],
        "tick_type": [1, 1, 2],
    }


@mark.unit
def test_decode_shioaji_historical_ticks_preserves_provider_order() -> None:
    sdk_observation, transactions = decode_shioaji_historical_ticks(
        payload=_payload(),
        request=_request(),
        security=_security(),
        provider_version="1.7.7",
    )

    decoded = json.loads(sdk_observation)
    assert decoded == {
        "payload": _payload(),
        "provider": "shioaji",
        "provider_version": "1.7.7",
        "request": {
            "query_type": "RangeTime",
            "session_date": "2026-09-24",
            "source_symbol": "2330",
            "time_end_local": "13:30:59",
            "time_start_local": "09:00:00",
        },
    }
    assert sdk_observation.endswith(b"\n")

    assert tuple(tick["observed_at_utc"] for tick in transactions) == (
        datetime(
            2026,
            9,
            24,
            1,
            0,
            3,
            123456,
            tzinfo=timezone.utc,
        ),
        datetime(
            2026,
            9,
            24,
            1,
            0,
            3,
            123456,
            tzinfo=timezone.utc,
        ),
        datetime(2026, 9, 24, 5, 30, 0, tzinfo=timezone.utc),
    )
    assert tuple(tick["price"] for tick in transactions) == (
        2480.0,
        2480.5,
        2475.0,
    )
    assert tuple(tick["volume"] for tick in transactions) == (
        1000.0,
        2000.0,
        3000.0,
    )
    assert all(tick["security"] == _security() for tick in transactions)
    assert all(
        tick["session_date"] == date(2026, 9, 24)
        for tick in transactions
    )

    repeated_bytes, repeated_transactions = decode_shioaji_historical_ticks(
        payload=_payload(),
        request=_request(),
        security=_security(),
        provider_version="1.7.7",
    )
    assert repeated_bytes == sdk_observation
    assert repeated_transactions == transactions


@mark.unit
def test_decode_shioaji_historical_ticks_rejects_invalid_payloads() -> None:
    missing_field = _payload()
    del missing_field["tick_type"]
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_historical_ticks(
            payload=missing_field,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )

    inconsistent = _payload()
    inconsistent["close"] = [2480.0]
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_historical_ticks(
            payload=inconsistent,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )

    empty = {
        field: []
        for field in (
            "ts",
            "close",
            "volume",
            "bid_price",
            "bid_volume",
            "ask_price",
            "ask_volume",
            "tick_type",
        )
    }
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_historical_ticks(
            payload=empty,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )

    boolean_price = deepcopy(_payload())
    boolean_price["close"][0] = True
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_historical_ticks(
            payload=boolean_price,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )

    non_finite = deepcopy(_payload())
    non_finite["ask_price"][0] = float("inf")
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_historical_ticks(
            payload=non_finite,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )

    non_microsecond_timestamp = deepcopy(_payload())
    non_microsecond_timestamp["ts"][0] += 1
    with raises(InvalidProviderCaptureInputError):
        decode_shioaji_historical_ticks(
            payload=non_microsecond_timestamp,
            request=_request(),
            security=_security(),
            provider_version="1.7.7",
        )
