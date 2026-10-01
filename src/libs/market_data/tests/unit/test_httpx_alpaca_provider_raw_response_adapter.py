from datetime import datetime, timezone

import httpx
from pytest import mark, raises

from libs.market_data.adapters.driven.httpx_alpaca_provider_raw_response_adapter import (
    HttpxAlpacaProviderRawResponseAdapter,
)
from libs.market_data.exceptions.provider_transport_error import (
    ProviderTransportError,
)
from libs.market_data.services.build_alpaca_historical_bars_request import (
    build_alpaca_historical_bars_request,
)


@mark.unit
def test_httpx_alpaca_provider_raw_response_adapter() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=b'{"symbol":"AAPL","bars":[],"next_page_token":null}',
        )

    request = build_alpaca_historical_bars_request(
        source_symbol="AAPL",
        session_start_utc=datetime(2024, 7, 2, 13, 30, tzinfo=timezone.utc),
        session_end_utc_exclusive=datetime(2024, 7, 2, 20, 0, tzinfo=timezone.utc),
        price_basis="as_printed",
    )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id="key-id",
            secret_key="secret",
            allow_live=True,
        )
        raw = adapter(provider="alpaca", request=request)

    assert raw.startswith(b"{")
    assert len(seen) == 1
    assert seen[0].headers["APCA-API-KEY-ID"] == "key-id"
    assert seen[0].headers["APCA-API-SECRET-KEY"] == "secret"
    assert seen[0].url.host == "data.alpaca.markets"

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        disabled = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id="key-id",
            secret_key="secret",
            allow_live=False,
        )
        with raises(Exception):
            disabled(provider="alpaca", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        missing = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id="",
            secret_key="secret",
            allow_live=True,
        )
        with raises(ProviderTransportError):
            missing(provider="alpaca", request=request)
