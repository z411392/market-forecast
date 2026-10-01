from datetime import date, datetime
from typing import get_args, get_type_hints

from pytest import mark

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.session_open_price_observation import SessionOpenPriceObservation


@mark.contract
def test_session_open_price_observation_contract() -> None:
    assert SessionOpenPriceObservation.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "source_interval_start_utc",
            "price",
            "price_basis",
        }
    )

    hints = get_type_hints(SessionOpenPriceObservation)
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert hints["source_interval_start_utc"] is datetime
    assert hints["price"] is float
    assert get_args(hints["price_basis"]) == ("as_printed", "split_adjusted")
