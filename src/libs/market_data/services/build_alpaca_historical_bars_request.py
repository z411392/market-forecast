import re
from datetime import datetime, timedelta
from typing import Literal

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)

_ALPACA_SOURCE_SYMBOL = re.compile(r"[A-Z0-9.-]+\Z")


def build_alpaca_historical_bars_request(
    *,
    source_symbol: str,
    session_start_utc: datetime,
    session_end_utc_exclusive: datetime,
    price_basis: Literal["as_printed", "split_adjusted"],
) -> ProviderRequestSpec:
    if not isinstance(source_symbol, str) or _ALPACA_SOURCE_SYMBOL.fullmatch(source_symbol) is None:
        raise InvalidProviderRequestInputError("invalid_alpaca_source_symbol")
    if not _is_utc_minute(session_start_utc):
        raise InvalidProviderRequestInputError("invalid_alpaca_session_start_utc")
    if not _is_utc_minute(session_end_utc_exclusive):
        raise InvalidProviderRequestInputError("invalid_alpaca_session_end_utc")
    if session_end_utc_exclusive <= session_start_utc:
        raise InvalidProviderRequestInputError("invalid_alpaca_session_window")
    if price_basis not in ("as_printed", "split_adjusted"):
        raise InvalidProviderRequestInputError("invalid_alpaca_price_basis")

    request_end = session_end_utc_exclusive - timedelta(seconds=1)
    adjustment = "raw" if price_basis == "as_printed" else "split"
    return {
        "method": "GET",
        "path": f"/v2/stocks/{source_symbol}/bars",
        "query": (
            ("timeframe", "1Min"),
            ("start", _format_utc(session_start_utc)),
            ("end", _format_utc(request_end)),
            ("adjustment", adjustment),
            ("feed", "sip"),
            ("sort", "asc"),
            ("limit", "10000"),
        ),
    }


def _is_utc_minute(value: datetime) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
        and value.second == 0
        and value.microsecond == 0
    )


def _format_utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
