from datetime import datetime, timedelta, timezone

from pytest import mark, raises

from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)
from libs.market_data.services.build_massive_regular_session_minute_request import (
    build_massive_regular_session_minute_request,
)


@mark.unit
def test_build_massive_regular_session_minute_request() -> None:
    start = datetime(2024, 7, 2, 13, 30, tzinfo=timezone.utc)
    end_exclusive = datetime(2024, 7, 2, 20, 0, tzinfo=timezone.utc)

    assert build_massive_regular_session_minute_request(
        source_symbol="AAPL",
        session_start_utc=start,
        session_end_utc_exclusive=end_exclusive,
        price_basis="as_printed",
    ) == {
        "method": "GET",
        "path": (
            "/v2/aggs/ticker/AAPL/range/1/minute/"
            "1719927000000/1719950399999"
        ),
        "query": (
            ("adjusted", "false"),
            ("sort", "asc"),
            ("limit", "50000"),
        ),
    }

    split_adjusted = build_massive_regular_session_minute_request(
        source_symbol="NVDA",
        session_start_utc=start,
        session_end_utc_exclusive=end_exclusive,
        price_basis="split_adjusted",
    )
    assert split_adjusted["query"][0] == ("adjusted", "true")

    with raises(InvalidProviderRequestInputError):
        build_massive_regular_session_minute_request(
            source_symbol="aapl",
            session_start_utc=start,
            session_end_utc_exclusive=end_exclusive,
            price_basis="as_printed",
        )
    with raises(InvalidProviderRequestInputError):
        build_massive_regular_session_minute_request(
            source_symbol="AAPL",
            session_start_utc=start.replace(tzinfo=None),
            session_end_utc_exclusive=end_exclusive,
            price_basis="as_printed",
        )
    with raises(InvalidProviderRequestInputError):
        build_massive_regular_session_minute_request(
            source_symbol="AAPL",
            session_start_utc=start,
            session_end_utc_exclusive=start,
            price_basis="as_printed",
        )
    with raises(InvalidProviderRequestInputError):
        build_massive_regular_session_minute_request(
            source_symbol="AAPL",
            session_start_utc=start,
            session_end_utc_exclusive=end_exclusive,
            price_basis="invalid",  # type: ignore[arg-type]
        )
    with raises(InvalidProviderRequestInputError):
        build_massive_regular_session_minute_request(
            source_symbol="AAPL",
            session_start_utc=start + timedelta(microseconds=1),
            session_end_utc_exclusive=end_exclusive,
            price_basis="as_printed",
        )
