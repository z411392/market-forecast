import json
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256

from pytest import mark, raises

from libs.market_data.dtos.canonical_transaction_tick import CanonicalTransactionTick
from libs.market_data.dtos.historical_tick_request_spec import HistoricalTickRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)
from libs.market_data.services.build_tick_day_evidence import build_tick_day_evidence
from libs.realized_variance.constants.taiwan_realized_kernel_estimator_version import (
    TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _request() -> HistoricalTickRequestSpec:
    return {
        "provider": "shioaji",
        "source_symbol": "2330",
        "session_date": date(2026, 9, 24),
        "query_type": "RangeTime",
        "time_start_local": time(9, 0),
        "time_end_local": time(13, 30, 59),
    }


def _transactions() -> tuple[CanonicalTransactionTick, ...]:
    security = _security()
    session_date = date(2026, 9, 24)
    duplicate_time = datetime(2026, 9, 24, 1, 0, 3, tzinfo=timezone.utc)
    return (
        {
            "security": security,
            "session_date": session_date,
            "observed_at_utc": duplicate_time,
            "price": 2480.0,
            "volume": 10.0,
        },
        {
            "security": security,
            "session_date": session_date,
            "observed_at_utc": duplicate_time,
            "price": 2481.0,
            "volume": 5.0,
        },
        {
            "security": security,
            "session_date": session_date,
            "observed_at_utc": datetime(
                2026,
                9,
                24,
                5,
                29,
                59,
                tzinfo=timezone.utc,
            ),
            "price": 2476.0,
            "volume": 3.0,
        },
        {
            "security": security,
            "session_date": session_date,
            "observed_at_utc": datetime(
                2026,
                9,
                24,
                5,
                30,
                tzinfo=timezone.utc,
            ),
            "price": 2475.0,
            "volume": 20.0,
        },
    )


@mark.unit
def test_build_tick_day_evidence() -> None:
    request = _request()
    sdk_observation = b'{"provider":"shioaji","rows":4}\n'

    transaction_bytes, receipt = build_tick_day_evidence(
        request=request,
        security=_security(),
        provider_version="1.7.7",
        sdk_observation=sdk_observation,
        transactions=_transactions(),
    )

    expected_request_bytes = (
        b'{"provider":"shioaji","query_type":"RangeTime",'
        b'"session_date":"2026-09-24","source_symbol":"2330",'
        b'"time_end_local":"13:30:59","time_start_local":"09:00:00"}\n'
    )
    assert build_historical_tick_request_sha256(request) == sha256(
        expected_request_bytes
    ).hexdigest()

    expected_transactions = {
        "security": _security(),
        "session_date": "2026-09-24",
        "source_symbol": "2330",
        "transactions": [
            {
                "observed_at_utc": tick["observed_at_utc"].isoformat(),
                "price": tick["price"],
                "volume": tick["volume"],
            }
            for tick in _transactions()
        ],
    }
    expected_transaction_bytes = (
        json.dumps(
            expected_transactions,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    assert transaction_bytes == expected_transaction_bytes
    assert receipt["provider"] == "shioaji"
    assert receipt["provider_version"] == "1.7.7"
    assert receipt["source_symbol"] == "2330"
    assert receipt["security"] == _security()
    assert receipt["session_date"] == date(2026, 9, 24)
    assert receipt["request"] == request
    assert receipt["request_sha256"] == sha256(expected_request_bytes).hexdigest()
    assert receipt["sdk_observation_sha256"] == sha256(sdk_observation).hexdigest()
    assert receipt["transaction_sequence_sha256"] == sha256(
        expected_transaction_bytes
    ).hexdigest()
    assert receipt["estimator_version"] == TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION
    assert receipt["tick_count"] == 4
    assert receipt["first_observed_at_utc"] == _transactions()[0]["observed_at_utc"]
    assert receipt["last_observed_at_utc"] == _transactions()[-1]["observed_at_utc"]
    assert receipt["opening_price"] == 2480.0
    assert receipt["closing_auction_observed_at_utc"] == _transactions()[-1][
        "observed_at_utc"
    ]
    assert receipt["closing_auction_price"] == 2475.0
    assert receipt["duplicate_timestamp_adjacency_count"] == 1


@mark.unit
def test_build_tick_day_evidence_rejects_invalid_inputs() -> None:
    request = _request()
    security = _security()
    transactions = _transactions()
    sdk_observation = b'{"provider":"shioaji","rows":4}\n'

    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="",
            sdk_observation=sdk_observation,
            transactions=transactions,
        )
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=b"",
            transactions=transactions,
        )
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=(),
        )

    wrong_session_tick = {
        **transactions[0],
        "session_date": date(2026, 9, 23),
    }
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=(wrong_session_tick, *transactions[1:]),
        )

    naive_tick = {
        **transactions[0],
        "observed_at_utc": transactions[0]["observed_at_utc"].replace(tzinfo=None),
    }
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=(naive_tick, *transactions[1:]),
        )

    outside_session_tick = {
        **transactions[0],
        "observed_at_utc": datetime(
            2026,
            9,
            24,
            0,
            59,
            59,
            tzinfo=timezone.utc,
        ),
    }
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=(outside_session_tick, *transactions[1:]),
        )

    decreasing = (transactions[1], transactions[0], *transactions[2:])
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=decreasing,
        )

    bad_price = ({**transactions[0], "price": 0.0}, *transactions[1:])
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=bad_price,
        )

    bad_volume = ({**transactions[0], "volume": 0.0}, *transactions[1:])
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=bad_volume,
        )

    missing_close = transactions[:-1]
    with raises(InvalidProviderCaptureInputError):
        build_tick_day_evidence(
            request=request,
            security=security,
            provider_version="1.7.7",
            sdk_observation=sdk_observation,
            transactions=missing_close,
        )

    invalid_request = {
        **request,
        "time_start_local": time(9, 1),
    }
    with raises(InvalidProviderCaptureInputError):
        build_historical_tick_request_sha256(invalid_request)
