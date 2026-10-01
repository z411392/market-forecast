import re
from datetime import date

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)


_MASSIVE_SOURCE_SYMBOL = re.compile(r"[A-Z0-9.-]+\Z")


def build_massive_minute_request(
    source_symbol: str,
    session_date: date,
) -> ProviderRequestSpec:
    if not isinstance(source_symbol, str) or _MASSIVE_SOURCE_SYMBOL.fullmatch(source_symbol) is None:
        raise InvalidProviderRequestInputError("invalid_massive_source_symbol")
    if type(session_date) is not date:
        raise InvalidProviderRequestInputError("invalid_session_date")

    date_text = session_date.isoformat()
    return {
        "method": "GET",
        "path": (f"/v2/aggs/ticker/{source_symbol}/range/1/minute/" f"{date_text}/{date_text}"),
        "query": (
            ("adjusted", "false"),
            ("sort", "asc"),
            ("limit", "50000"),
        ),
    }
