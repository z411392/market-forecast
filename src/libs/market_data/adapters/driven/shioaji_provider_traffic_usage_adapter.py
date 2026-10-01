from typing import Any

from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError
from libs.market_data.ports.read_provider_traffic_usage_port import (
    ReadProviderTrafficUsagePort,
)


class ShioajiProviderTrafficUsageAdapter(ReadProviderTrafficUsagePort):
    def __init__(self, api: Any) -> None:
        self._api = api

    def __call__(self) -> ProviderTrafficUsage:
        try:
            raw = self._api.usage()
        except Exception as error:
            raise ProviderTransportError(
                "shioaji_provider_usage_fetch_failed"
            ) from error

        try:
            used = raw.bytes
            limit = raw.limit_bytes
            remaining = raw.remaining_bytes
        except AttributeError as error:
            raise ProviderTransportError(
                "shioaji_provider_usage_invalid_result"
            ) from error

        if (
            type(used) is not int
            or type(limit) is not int
            or type(remaining) is not int
            or used < 0
            or limit <= 0
            or remaining < 0
            or used > limit
            or remaining > limit
        ):
            raise ProviderTransportError(
                "shioaji_provider_usage_invalid_result"
            )

        return {
            "used_bytes": used,
            "limit_bytes": limit,
            "remaining_bytes": remaining,
        }
