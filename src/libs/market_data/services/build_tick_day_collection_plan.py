from datetime import date, time

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_collection_item import TickDayCollectionItem
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


def build_tick_day_collection_plan(
    *,
    session_dates: tuple[date, ...],
    securities: tuple[SecurityIdentity, ...],
) -> tuple[TickDayCollectionItem, ...]:
    _validate_session_dates(session_dates)
    _validate_securities(securities)

    items: list[TickDayCollectionItem] = []
    for session_date in session_dates:
        for security in securities:
            items.append(
                {
                    "request": {
                        "provider": "shioaji",
                        "source_symbol": security["symbol"],
                        "session_date": session_date,
                        "query_type": "RangeTime",
                        "time_start_local": time(9, 0, 0),
                        "time_end_local": time(13, 30, 59),
                    },
                    "security": security,
                }
            )
    return tuple(items)


def _validate_session_dates(session_dates: tuple[date, ...]) -> None:
    if not session_dates:
        raise InvalidProviderCaptureInputError(
            "tick_collection_plan_empty_sessions"
        )

    previous: date | None = None
    for session_date in session_dates:
        if type(session_date) is not date:
            raise InvalidProviderCaptureInputError(
                "tick_collection_plan_invalid_session_date"
            )
        if previous is not None and session_date <= previous:
            raise InvalidProviderCaptureInputError(
                "tick_collection_plan_sessions_not_strictly_increasing"
            )
        previous = session_date


def _validate_securities(
    securities: tuple[SecurityIdentity, ...],
) -> None:
    if not securities:
        raise InvalidProviderCaptureInputError(
            "tick_collection_plan_empty_securities"
        )

    seen_symbols: set[str] = set()
    for security in securities:
        symbol = security["symbol"]
        if not isinstance(symbol, str) or not symbol:
            raise InvalidProviderCaptureInputError(
                "tick_collection_plan_invalid_symbol"
            )
        if symbol in seen_symbols:
            raise InvalidProviderCaptureInputError(
                "tick_collection_plan_duplicate_symbol"
            )
        if (
            security["exchange"] != "XTAI"
            or security["timezone"] != "Asia/Taipei"
            or security["calendar_id"] != "XTAI"
        ):
            raise InvalidProviderCaptureInputError(
                "tick_collection_plan_invalid_security_identity"
            )
        seen_symbols.add(symbol)
