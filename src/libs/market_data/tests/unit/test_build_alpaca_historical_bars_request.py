from datetime import datetime, timezone

from pytest import mark, raises

from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)
from libs.market_data.services.build_alpaca_historical_bars_request import (
    build_alpaca_historical_bars_request,
)


@mark.unit
def test_build_alpaca_historical_bars_request() -> None:
    start = datetime(2024, 7, 2, 13, 30, tzinfo=timezone.utc)
    end = datetime(2024, 7, 2, 20, 0, tzinfo=timezone.utc)

    assert build_alpaca_historical_bars_request(
        source_symbol="AAPL",
        session_start_utc=start,
        session_end_utc_exclusive=end,
        price_basis="as_printed",
    ) == {
        "method": "GET",
        "path": "/v2/stocks/AAPL/bars",
        "query": (
            ("timeframe", "1Min"),
            ("start", "2024-07-02T13:30:00Z"),
            ("end", "2024-07-02T19:59:59Z"),
            ("adjustment", "raw"),
            ("feed", "sip"),
            ("sort", "asc"),
            ("limit", "10000"),
        ),
    }

    split_request = build_alpaca_historical_bars_request(
        source_symbol="NVDA",
        session_start_utc=start,
        session_end_utc_exclusive=end,
        price_basis="split_adjusted",
    )
    assert ("adjustment", "split") in split_request["query"]

    with raises(InvalidProviderRequestInputError):
        build_alpaca_historical_bars_request(
            source_symbol="aapl",
            session_start_utc=start,
            session_end_utc_exclusive=end,
            price_basis="as_printed",
        )
    with raises(InvalidProviderRequestInputError):
        build_alpaca_historical_bars_request(
            source_symbol="AAPL",
            session_start_utc=start.replace(tzinfo=None),
            session_end_utc_exclusive=end,
            price_basis="as_printed",
        )
    with raises(InvalidProviderRequestInputError):
        build_alpaca_historical_bars_request(
            source_symbol="AAPL",
            session_start_utc=start,
            session_end_utc_exclusive=start,
            price_basis="as_printed",
        )
