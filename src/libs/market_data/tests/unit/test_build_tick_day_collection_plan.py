from datetime import date, time

from pytest import mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_tick_day_collection_plan import (
    build_tick_day_collection_plan,
)


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


@mark.unit
def test_build_tick_day_collection_plan_is_session_major_and_symbol_minor() -> None:
    sessions = (
        date(2025, 9, 10),
        date(2025, 9, 11),
    )
    securities = (
        _security("2330"),
        _security("2317"),
        _security("2454"),
    )

    plan = build_tick_day_collection_plan(
        session_dates=sessions,
        securities=securities,
    )

    assert len(plan) == 6
    assert tuple(
        (
            item["request"]["session_date"],
            item["request"]["source_symbol"],
        )
        for item in plan
    ) == (
        (date(2025, 9, 10), "2330"),
        (date(2025, 9, 10), "2317"),
        (date(2025, 9, 10), "2454"),
        (date(2025, 9, 11), "2330"),
        (date(2025, 9, 11), "2317"),
        (date(2025, 9, 11), "2454"),
    )

    for item in plan:
        assert item["request"]["provider"] == "shioaji"
        assert item["request"]["query_type"] == "RangeTime"
        assert item["request"]["time_start_local"] == time(9, 0)
        assert item["request"]["time_end_local"] == time(13, 30, 59)
        assert item["request"]["source_symbol"] == item["security"]["symbol"]


@mark.unit
def test_build_tick_day_collection_plan_rejects_invalid_supplied_order() -> None:
    valid_securities = (
        _security("2330"),
        _security("2317"),
        _security("2454"),
    )

    invalid_cases = (
        {
            "session_dates": (),
            "securities": valid_securities,
        },
        {
            "session_dates": (
                date(2025, 9, 11),
                date(2025, 9, 10),
            ),
            "securities": valid_securities,
        },
        {
            "session_dates": (
                date(2025, 9, 10),
                date(2025, 9, 10),
            ),
            "securities": valid_securities,
        },
        {
            "session_dates": (date(2025, 9, 10),),
            "securities": (),
        },
        {
            "session_dates": (date(2025, 9, 10),),
            "securities": (
                _security("2330"),
                _security("2330"),
            ),
        },
        {
            "session_dates": (date(2025, 9, 10),),
            "securities": (
                {
                    **_security("2330"),
                    "calendar_id": "XNYS",
                },
            ),
        },
    )

    for case in invalid_cases:
        with raises(InvalidProviderCaptureInputError):
            build_tick_day_collection_plan(
                session_dates=case["session_dates"],
                securities=case["securities"],
            )
