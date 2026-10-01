from typing import Literal

import httpx

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.live_provider_request_not_authorized_error import (
    LiveProviderRequestNotAuthorizedError,
)
from libs.market_data.exceptions.provider_transport_error import (
    ProviderTransportError,
)
from libs.market_data.ports.fetch_provider_raw_response_port import (
    FetchProviderRawResponsePort,
)


class HttpxAlpacaProviderRawResponseAdapter(FetchProviderRawResponsePort):
    def __init__(
        self,
        *,
        client: httpx.Client,
        api_key_id: str | None,
        secret_key: str | None,
        allow_live: bool = False,
    ) -> None:
        self._client = client
        self._api_key_id = api_key_id
        self._secret_key = secret_key
        self._allow_live = allow_live

    def __call__(
        self,
        provider: Literal["massive", "finmind", "alpaca"],
        request: ProviderRequestSpec,
    ) -> bytes:
        if not self._allow_live:
            raise LiveProviderRequestNotAuthorizedError()
        if provider != "alpaca":
            raise ProviderTransportError("unsupported_provider")
        if self._api_key_id is None or not self._api_key_id.strip():
            raise ProviderTransportError("missing_provider_credential")
        if self._secret_key is None or not self._secret_key.strip():
            raise ProviderTransportError("missing_provider_credential")

        try:
            response = self._client.request(
                request["method"],
                f"https://data.alpaca.markets{request['path']}",
                params=request["query"],
                headers={
                    "APCA-API-KEY-ID": self._api_key_id,
                    "APCA-API-SECRET-KEY": self._secret_key,
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError:
            raise ProviderTransportError("provider_transport_error") from None

        if not 200 <= response.status_code < 300:
            raise ProviderTransportError("provider_http_error")
        return response.content
