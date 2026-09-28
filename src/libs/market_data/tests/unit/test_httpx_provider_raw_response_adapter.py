from datetime import date

import httpx
from pytest import mark, raises

from libs.market_data.adapters.driven.httpx_provider_raw_response_adapter import (
    HttpxProviderRawResponseAdapter,
)
from libs.market_data.exceptions.live_provider_request_not_authorized_error import (
    LiveProviderRequestNotAuthorizedError,
)
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError
from libs.market_data.services.build_finmind_stock_kbar_request import (
    build_finmind_stock_kbar_request,
)
from libs.market_data.services.build_massive_minute_request import (
    build_massive_minute_request,
)


def _adapter(
    transport: httpx.MockTransport,
    *,
    allow_live: bool,
    massive_api_key: str | None = "test-massive-key",
    finmind_token: str | None = "test-finmind-token",
) -> HttpxProviderRawResponseAdapter:
    return HttpxProviderRawResponseAdapter(
        client=httpx.Client(transport=transport),
        massive_base_url="https://api.massive.test",
        finmind_base_url="https://api.finmind.test",
        massive_api_key=massive_api_key,
        finmind_token=finmind_token,
        allow_live=allow_live,
    )


@mark.unit
def test_httpx_provider_raw_response_adapter() -> None:
    requests: list[httpx.Request] = []

    def ok_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b'{"status":"ok"}')

    transport = httpx.MockTransport(ok_handler)
    disabled = _adapter(transport, allow_live=False)
    with raises(
        LiveProviderRequestNotAuthorizedError,
        match="live_provider_request_not_authorized",
    ):
        disabled(
            provider="massive",
            request=build_massive_minute_request("AAPL", date(2024, 7, 2)),
        )
    assert requests == []

    enabled = _adapter(transport, allow_live=True)
    massive_request = build_massive_minute_request("AAPL", date(2024, 7, 2))
    massive_raw = enabled(provider="massive", request=massive_request)
    assert massive_raw == b'{"status":"ok"}'
    assert len(requests) == 1
    assert requests[-1].url.host == "api.massive.test"
    assert requests[-1].url.path == massive_request["path"]
    assert tuple(requests[-1].url.params.multi_items()) == massive_request["query"]
    assert requests[-1].headers["Authorization"] == "Bearer test-massive-key"
    assert "test-massive-key" not in str(requests[-1].url)

    finmind_request = build_finmind_stock_kbar_request("2330", date(2026, 9, 24))
    finmind_raw = enabled(provider="finmind", request=finmind_request)
    assert finmind_raw == b'{"status":"ok"}'
    assert len(requests) == 2
    assert requests[-1].url.host == "api.finmind.test"
    assert requests[-1].url.path == finmind_request["path"]
    assert tuple(requests[-1].url.params.multi_items()) == finmind_request["query"]
    assert requests[-1].headers["Authorization"] == "Bearer test-finmind-token"
    assert "test-finmind-token" not in str(requests[-1].url)

    missing = _adapter(transport, allow_live=True, massive_api_key=None)
    with raises(ProviderTransportError, match="missing_provider_credential"):
        missing(provider="massive", request=massive_request)
    assert len(requests) == 2

    def error_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401, content=b"sensitive-provider-body")

    failing = _adapter(httpx.MockTransport(error_handler), allow_live=True)
    with raises(ProviderTransportError) as caught:
        failing(provider="massive", request=massive_request)
    assert str(caught.value) == "provider_http_error"
    assert "sensitive-provider-body" not in str(caught.value)
    assert "api.massive.test" not in str(caught.value)
