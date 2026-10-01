from pytest import mark, raises

from libs.market_data.adapters.driven.shioaji_provider_traffic_usage_adapter import (
    ShioajiProviderTrafficUsageAdapter,
)
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError


class _Usage:
    def __init__(
        self,
        *,
        used_bytes: object,
        limit_bytes: object,
        remaining_bytes: object,
    ) -> None:
        self.bytes = used_bytes
        self.limit_bytes = limit_bytes
        self.remaining_bytes = remaining_bytes


class _Api:
    def __init__(
        self,
        *,
        usage: object,
        error: Exception | None = None,
    ) -> None:
        self.usage_value = usage
        self.error = error
        self.calls = 0

    def usage(self) -> object:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.usage_value


@mark.unit
def test_shioaji_provider_traffic_usage_adapter_normalizes_cumulative_usage() -> None:
    api = _Api(
        usage=_Usage(
            used_bytes=22_287_469,
            limit_bytes=524_288_000,
            remaining_bytes=502_000_531,
        )
    )

    result = ShioajiProviderTrafficUsageAdapter(api)()

    assert result == {
        "used_bytes": 22_287_469,
        "limit_bytes": 524_288_000,
        "remaining_bytes": 502_000_531,
    }
    assert api.calls == 1


@mark.unit
def test_shioaji_provider_traffic_usage_adapter_fails_closed() -> None:
    invalid_values = (
        _Usage(
            used_bytes=True,
            limit_bytes=500,
            remaining_bytes=499,
        ),
        _Usage(
            used_bytes=-1,
            limit_bytes=500,
            remaining_bytes=501,
        ),
        _Usage(
            used_bytes=10,
            limit_bytes=0,
            remaining_bytes=0,
        ),
        _Usage(
            used_bytes=501,
            limit_bytes=500,
            remaining_bytes=0,
        ),
        _Usage(
            used_bytes=10,
            limit_bytes=500,
            remaining_bytes=501,
        ),
    )
    for usage in invalid_values:
        with raises(ProviderTransportError):
            ShioajiProviderTrafficUsageAdapter(_Api(usage=usage))()

    with raises(ProviderTransportError):
        ShioajiProviderTrafficUsageAdapter(
            _Api(
                usage=_Usage(
                    used_bytes=0,
                    limit_bytes=500,
                    remaining_bytes=500,
                ),
                error=RuntimeError("usage failed"),
            )
        )()
