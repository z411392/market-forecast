from typing import get_args, get_origin, get_type_hints

from pytest import mark

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.invalid_provider_request_input_error import (
    InvalidProviderRequestInputError,
)


@mark.contract
def test_provider_request_spec_contract() -> None:
    assert ProviderRequestSpec.__required_keys__ == frozenset(
        {
            "method",
            "path",
            "query",
        }
    )

    hints = get_type_hints(ProviderRequestSpec)
    assert get_args(hints["method"]) == ("GET",)
    assert hints["path"] is str

    query_hint = hints["query"]
    assert get_origin(query_hint) is tuple
    query_item_hint, variadic = get_args(query_hint)
    assert variadic is Ellipsis
    assert get_origin(query_item_hint) is tuple
    assert get_args(query_item_hint) == (str, str)

    assert issubclass(InvalidProviderRequestInputError, ValueError)
    assert InvalidProviderRequestInputError.type == "invalid_provider_request_input"
