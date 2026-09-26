from inspect import isabstract
from typing import get_args, get_origin, get_type_hints

from libs.market_data.dtos.corporate_action_fact import CorporateActionFact
from libs.market_data.dtos.corporate_actions_query import CorporateActionsQuery
from libs.market_data.dtos.minute_bars_batch import MinuteBarsBatch
from libs.market_data.dtos.minute_bars_query import MinuteBarsQuery
from libs.market_data.exceptions.invalid_market_data_contract_error import (
    InvalidMarketDataContractError,
)
from libs.market_data.ports.read_corporate_actions_port import ReadCorporateActionsPort
from libs.market_data.ports.read_minute_bars_port import ReadMinuteBarsPort
from pytest import mark


@mark.contract
def test_market_data_ports_contract() -> None:
    assert isabstract(ReadMinuteBarsPort)
    assert ReadMinuteBarsPort.__abstractmethods__ == frozenset({"__call__"})
    minute_hints = get_type_hints(ReadMinuteBarsPort.__call__)
    assert minute_hints["query"] is MinuteBarsQuery
    assert minute_hints["return"] is MinuteBarsBatch

    assert isabstract(ReadCorporateActionsPort)
    assert ReadCorporateActionsPort.__abstractmethods__ == frozenset({"__call__"})
    action_hints = get_type_hints(ReadCorporateActionsPort.__call__)
    assert action_hints["query"] is CorporateActionsQuery
    assert get_origin(action_hints["return"]) is tuple
    assert get_args(action_hints["return"]) == (CorporateActionFact, Ellipsis)

    assert issubclass(InvalidMarketDataContractError, ValueError)
    assert InvalidMarketDataContractError.type == "invalid_market_data_contract"
