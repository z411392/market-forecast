from datetime import date, datetime
from typing import get_args, get_type_hints

from pytest import mark

from libs.market_data.dtos.closing_auction_observation import ClosingAuctionObservation
from libs.market_data.dtos.security_identity import SecurityIdentity


@mark.contract
def test_closing_auction_observation_contract() -> None:
    assert ClosingAuctionObservation.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "matched_at_utc",
            "price",
            "volume",
            "price_basis",
        }
    )

    hints = get_type_hints(ClosingAuctionObservation)
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert hints["matched_at_utc"] is datetime
    assert hints["price"] is float
    assert hints["volume"] is float
    assert get_args(hints["price_basis"]) == ("as_printed", "split_adjusted")
