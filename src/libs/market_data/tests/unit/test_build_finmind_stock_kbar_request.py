from datetime import date, datetime, timezone

from pytest import mark, raises

from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)
from libs.market_data.services.build_finmind_stock_kbar_request import (
    build_finmind_stock_kbar_request,
)


@mark.unit
def test_build_finmind_stock_kbar_request() -> None:
    session_date = date(2025, 11, 26)

    assert build_finmind_stock_kbar_request("2330", session_date) == {
        "method": "GET",
        "path": "/api/v4/data",
        "query": (
            ("dataset", "TaiwanStockKBar"),
            ("data_id", "2330"),
            ("start_date", "2025-11-26"),
        ),
    }

    for invalid_symbol in ("", " ", "2330.TW", "2330/1", "2330?x=1", "２３３０"):
        with raises(
            InvalidProviderRequestInputError,
            match="invalid_finmind_source_symbol",
        ):
            build_finmind_stock_kbar_request(invalid_symbol, session_date)

    with raises(
        InvalidProviderRequestInputError,
        match="invalid_session_date",
    ):
        build_finmind_stock_kbar_request(
            "2330",
            datetime(2025, 11, 26, tzinfo=timezone.utc),
        )  # type: ignore[arg-type]
