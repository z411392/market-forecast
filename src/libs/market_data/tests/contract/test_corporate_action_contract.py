from datetime import date
from typing import get_args, get_type_hints

from libs.market_data.dtos.corporate_action_fact import CorporateActionFact
from libs.market_data.dtos.corporate_actions_query import CorporateActionsQuery
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.source_provenance import SourceProvenance
from pytest import mark


@mark.contract
def test_corporate_action_contract() -> None:
    assert CorporateActionsQuery.__required_keys__ == frozenset(
        {"security", "start_date", "end_date"}
    )
    query_hints = get_type_hints(CorporateActionsQuery)
    assert query_hints["security"] is SecurityIdentity
    assert query_hints["start_date"] is date
    assert query_hints["end_date"] is date

    assert CorporateActionFact.__required_keys__ == frozenset(
        {"security", "action_type", "effective_date", "provenance"}
    )
    assert CorporateActionFact.__optional_keys__ == frozenset(
        {"ratio", "previous_symbol", "new_symbol", "cash_amount", "currency"}
    )
    fact_hints = get_type_hints(CorporateActionFact)
    assert fact_hints["security"] is SecurityIdentity
    assert get_args(fact_hints["action_type"]) == (
        "split",
        "symbol_change",
        "cash_dividend",
        "other",
    )
    assert fact_hints["effective_date"] is date
    assert fact_hints["provenance"] is SourceProvenance
    assert fact_hints["ratio"] is float
    assert fact_hints["previous_symbol"] is str
    assert fact_hints["new_symbol"] is str
    assert fact_hints["cash_amount"] is float
    assert fact_hints["currency"] is str
