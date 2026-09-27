import re
from datetime import date

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)


_FINMIND_SOURCE_SYMBOL = re.compile(r"[0-9]+\Z")


def build_finmind_stock_kbar_request(
    source_symbol: str,
    session_date: date,
) -> ProviderRequestSpec:
    if not isinstance(source_symbol, str) or _FINMIND_SOURCE_SYMBOL.fullmatch(source_symbol) is None:
        raise InvalidProviderRequestInputError("invalid_finmind_source_symbol")
    if type(session_date) is not date:
        raise InvalidProviderRequestInputError("invalid_session_date")

    return {
        "method": "GET",
        "path": "/api/v4/data",
        "query": (
            ("dataset", "TaiwanStockKBar"),
            ("data_id", source_symbol),
            ("start_date", session_date.isoformat()),
        ),
    }
