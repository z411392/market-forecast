from typing import Literal

import httpx

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.live_provider_request_not_authorized_error import (
    LiveProviderRequestNotAuthorizedError,
)
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError
from libs.market_data.ports.fetch_provider_raw_response_port import (
    FetchProviderRawResponsePort,
)


class HttpxProviderRawResponseAdapter(FetchProviderRawResponsePort):
    def __init__(
        self,
        client: httpx.Client,
        massive_base_url: str,
        finmind_base_url: str,
        massive_api_key: str | None,
        finmind_token: str | None,
        allow_live: bool = False,
    ) -> None:
        self._client = client
        self._massive_base_url = massive_base_url.rstrip("/")
        self._finmind_base_url = finmind_base_url.rstrip("/")
        self._massive_api_key = massive_api_key
        self._finmind_token = finmind_token
        self._allow_live = allow_live

    def __call__(
        self,
        provider: Literal["massive", "finmind", "alpaca"],
        request: ProviderRequestSpec,
    ) -> bytes:
        if not self._allow_live:
            raise LiveProviderRequestNotAuthorizedError()

        base_url, credential = self._provider_config(provider)
        if credential is None or not credential.strip():
            raise ProviderTransportError("missing_provider_credential")

        url = f"{base_url}{request['path']}"
        try:
            response = self._client.request(
                request["method"],
                url,
                params=request["query"],
                headers={"Authorization": f"Bearer {credential}"},
            )
        except httpx.HTTPError:
            raise ProviderTransportError("provider_transport_error") from None

        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderTransportError("provider_http_error")

        return response.content

    def _provider_config(
        self,
        provider: Literal["massive", "finmind", "alpaca"],
    ) -> tuple[str, str | None]:
        if provider == "massive":
            return self._massive_base_url, self._massive_api_key
        if provider == "finmind":
            return self._finmind_base_url, self._finmind_token
        raise ProviderTransportError("unsupported_provider")
