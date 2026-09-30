import importlib
from collections.abc import Mapping
from typing import Any

from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.exceptions.provider_transport_error import ProviderTransportError
from libs.market_data.ports.fetch_historical_tick_payload_port import (
    FetchHistoricalTickPayloadPort,
)


class ShioajiHistoricalTickPayloadAdapter(FetchHistoricalTickPayloadPort):
    def __init__(
        self,
        api: Any,
        *,
        range_time_query_type: object | None = None,
        timeout_ms: int = 15000,
    ) -> None:
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("timeout_ms must be a positive integer")
        self._api = api
        self._range_time_query_type = range_time_query_type
        self._timeout_ms = timeout_ms
        self._contracts: dict[str, object] = {}

    def __call__(
        self,
        request: HistoricalTickRequestSpec,
    ) -> Mapping[str, object]:
        if request["provider"] != "shioaji" or request["query_type"] != "RangeTime":
            raise ProviderTransportError(
                "shioaji_historical_tick_invalid_request"
            )

        symbol = request["source_symbol"]
        contract = self._contracts.get(symbol)
        if contract is None:
            try:
                contract = self._api.contracts.get(symbol)
            except Exception as error:
                raise ProviderTransportError(
                    "shioaji_historical_tick_contract_lookup_failed"
                ) from error
            if contract is None:
                raise ProviderTransportError(
                    "shioaji_historical_tick_contract_not_found"
                )
            self._contracts[symbol] = contract

        query_type = self._range_time_query_type
        if query_type is None:
            try:
                constant_module = importlib.import_module("shioaji.constant")
                ticks_query_type = getattr(
                    constant_module,
                    "TicksQueryType",
                )
                query_type = ticks_query_type.RangeTime
            except (ImportError, AttributeError) as error:
                raise ProviderTransportError(
                    "shioaji_sdk_unavailable"
                ) from error

        try:
            result = self._api.ticks(
                contract=contract,
                date=request["session_date"].isoformat(),
                query_type=query_type,
                time_start=request["time_start_local"],
                time_end=request["time_end_local"],
                timeout=self._timeout_ms,
            )
        except Exception as error:
            raise ProviderTransportError(
                "shioaji_historical_tick_fetch_failed"
            ) from error

        to_dict = getattr(result, "dict", None)
        if not callable(to_dict):
            raise ProviderTransportError(
                "shioaji_historical_tick_invalid_result"
            )
        try:
            payload = to_dict()
        except Exception as error:
            raise ProviderTransportError(
                "shioaji_historical_tick_invalid_result"
            ) from error
        if not isinstance(payload, Mapping):
            raise ProviderTransportError(
                "shioaji_historical_tick_invalid_result"
            )
        return payload
