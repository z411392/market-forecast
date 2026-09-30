from datetime import date, timedelta

from pytest import mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_tick_day_collection_plan import (
    build_tick_day_collection_plan,
)
from libs.market_data.services.partition_tick_day_collection_plan import (
    partition_tick_day_collection_plan,
)


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


@mark.unit
def test_partition_tick_day_collection_plan_preserves_complete_sessions() -> None:
    start = date(2025, 9, 10)
    sessions = tuple(start + timedelta(days=index) for index in range(5))
    plan = build_tick_day_collection_plan(
        session_dates=sessions,
        securities=(
            _security("2330"),
            _security("2317"),
            _security("2454"),
        ),
    )

    batches = partition_tick_day_collection_plan(
        items=plan,
        symbols_per_session=3,
        max_items=7,
    )

    assert tuple(len(batch) for batch in batches) == (6, 6, 3)
    assert tuple(
        batch[0]["request"]["session_date"]
        for batch in batches
    ) == (
        sessions[0],
        sessions[2],
        sessions[4],
    )
    assert tuple(
        batch[-1]["request"]["session_date"]
        for batch in batches
    ) == (
        sessions[1],
        sessions[3],
        sessions[4],
    )

    for batch in batches:
        by_date: dict[date, list[str]] = {}
        for item in batch:
            session_date = item["request"]["session_date"]
            by_date.setdefault(session_date, []).append(
                item["request"]["source_symbol"]
            )
        assert all(
            symbols == ["2330", "2317", "2454"]
            for symbols in by_date.values()
        )


@mark.unit
def test_partition_tick_day_collection_plan_rejects_invalid_boundaries() -> None:
    plan = build_tick_day_collection_plan(
        session_dates=(date(2025, 9, 10),),
        securities=(
            _security("2330"),
            _security("2317"),
            _security("2454"),
        ),
    )

    invalid_cases = (
        {
            "items": (),
            "symbols_per_session": 3,
            "max_items": 100,
        },
        {
            "items": plan,
            "symbols_per_session": 0,
            "max_items": 100,
        },
        {
            "items": plan,
            "symbols_per_session": 3,
            "max_items": 2,
        },
        {
            "items": plan[:-1],
            "symbols_per_session": 3,
            "max_items": 100,
        },
    )

    for case in invalid_cases:
        with raises(InvalidProviderCaptureInputError):
            partition_tick_day_collection_plan(
                items=case["items"],
                symbols_per_session=case["symbols_per_session"],
                max_items=case["max_items"],
            )
