import re
from datetime import datetime, timedelta
from typing import Literal

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)


_MASSIVE_SOURCE_SYMBOL = re.compile(r"[A-Z0-9.-]+\Z")


def build_massive_regular_session_minute_request(
    *,
    source_symbol: str,
    session_start_utc: datetime,
    session_end_utc_exclusive: datetime,
    price_basis: Literal["as_printed", "split_adjusted"],
) -> ProviderRequestSpec:
    if (
        not isinstance(source_symbol, str)
        or _MASSIVE_SOURCE_SYMBOL.fullmatch(source_symbol) is None
    ):
        raise InvalidProviderRequestInputError(
            "invalid_massive_source_symbol"
        )
    if not _is_utc_datetime(session_start_utc):
        raise InvalidProviderRequestInputError(
            "invalid_massive_session_start_utc"
        )
    if not _is_utc_datetime(session_end_utc_exclusive):
        raise InvalidProviderRequestInputError(
            "invalid_massive_session_end_utc"
        )
    if session_end_utc_exclusive <= session_start_utc:
        raise InvalidProviderRequestInputError(
            "invalid_massive_session_window"
        )
    if (
        session_start_utc.microsecond % 1000 != 0
        or session_end_utc_exclusive.microsecond % 1000 != 0
    ):
        raise InvalidProviderRequestInputError(
            "massive_session_bound_not_millisecond_aligned"
        )
    if price_basis not in ("as_printed", "split_adjusted"):
        raise InvalidProviderRequestInputError(
            "invalid_massive_price_basis"
        )

    start_ms = _unix_milliseconds(session_start_utc)
    end_exclusive_ms = _unix_milliseconds(
        session_end_utc_exclusive
    )
    end_inclusive_ms = end_exclusive_ms - 1

    return {
        "method": "GET",
        "path": (
            f"/v2/aggs/ticker/{source_symbol}/range/1/minute/"
            f"{start_ms}/{end_inclusive_ms}"
        ),
        "query": (
            (
                "adjusted",
                "false"
                if price_basis == "as_printed"
                else "true",
            ),
            ("sort", "asc"),
            ("limit", "50000"),
        ),
    }


def _is_utc_datetime(value: datetime) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
    )


def _unix_milliseconds(value: datetime) -> int:
    return (
        int(value.timestamp()) * 1000
        + value.microsecond // 1000
    )
