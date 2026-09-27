from datetime import date, datetime, timezone

from pytest import mark, raises

from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)
from libs.market_data.services.build_massive_minute_request import (
    build_massive_minute_request,
)


@mark.unit
def test_build_massive_minute_request() -> None:
    session_date = date(2025, 11, 26)

    assert build_massive_minute_request("AAPL", session_date) == {
        "method": "GET",
        "path": "/v2/aggs/ticker/AAPL/range/1/minute/2025-11-26/2025-11-26",
        "query": (
            ("adjusted", "false"),
            ("sort", "asc"),
            ("limit", "50000"),
        ),
    }

    assert build_massive_minute_request("BRK.B", session_date)["path"].startswith(
        "/v2/aggs/ticker/BRK.B/"
    )

    for invalid_symbol in ("", " ", "aapl", "AAPL/QQQ", "AAPL?x=1", "AAPL QQQ"):
        with raises(
            InvalidProviderRequestInputError,
            match="invalid_massive_source_symbol",
        ):
            build_massive_minute_request(invalid_symbol, session_date)

    with raises(
        InvalidProviderRequestInputError,
        match="invalid_session_date",
    ):
        build_massive_minute_request(
            "AAPL",
            datetime(2025, 11, 26, tzinfo=timezone.utc),
        )  # type: ignore[arg-type]
