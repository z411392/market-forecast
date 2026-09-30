from libs.market_data.dtos.tick_day_collection_item import TickDayCollectionItem
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


def partition_tick_day_collection_plan(
    *,
    items: tuple[TickDayCollectionItem, ...],
    symbols_per_session: int,
    max_items: int,
) -> tuple[tuple[TickDayCollectionItem, ...], ...]:
    if not items:
        raise InvalidProviderCaptureInputError(
            "tick_collection_partition_empty_plan"
        )
    if type(symbols_per_session) is not int or symbols_per_session <= 0:
        raise InvalidProviderCaptureInputError(
            "tick_collection_partition_invalid_symbols_per_session"
        )
    if type(max_items) is not int or max_items < symbols_per_session:
        raise InvalidProviderCaptureInputError(
            "tick_collection_partition_invalid_max_items"
        )
    if len(items) % symbols_per_session != 0:
        raise InvalidProviderCaptureInputError(
            "tick_collection_partition_incomplete_session_block"
        )

    _validate_session_blocks(items, symbols_per_session)

    batch_size = (max_items // symbols_per_session) * symbols_per_session
    return tuple(
        items[start : start + batch_size]
        for start in range(0, len(items), batch_size)
    )


def _validate_session_blocks(
    items: tuple[TickDayCollectionItem, ...],
    symbols_per_session: int,
) -> None:
    expected_symbols: tuple[str, ...] | None = None
    previous_session = None

    for start in range(0, len(items), symbols_per_session):
        block = items[start : start + symbols_per_session]
        session_dates = tuple(
            item["request"]["session_date"] for item in block
        )
        if len(set(session_dates)) != 1:
            raise InvalidProviderCaptureInputError(
                "tick_collection_partition_mixed_session_block"
            )
        session_date = session_dates[0]
        if previous_session is not None and session_date <= previous_session:
            raise InvalidProviderCaptureInputError(
                "tick_collection_partition_sessions_not_increasing"
            )

        symbols = tuple(
            item["request"]["source_symbol"] for item in block
        )
        if len(set(symbols)) != symbols_per_session:
            raise InvalidProviderCaptureInputError(
                "tick_collection_partition_duplicate_symbol_in_session"
            )
        if expected_symbols is None:
            expected_symbols = symbols
        elif symbols != expected_symbols:
            raise InvalidProviderCaptureInputError(
                "tick_collection_partition_symbol_order_changed"
            )

        previous_session = session_date
