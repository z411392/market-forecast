from datetime import date, datetime
from typing import get_args, get_type_hints

from pytest import mark

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.dtos.sampled_intraday_price import SampledIntradayPrice


@mark.contract
def test_sampled_intraday_price_contract() -> None:
    assert SampledIntradayPrice.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "observed_at_utc",
            "sampling_minutes",
            "role",
            "price",
            "price_basis",
            "algorithm_version",
        }
    )

    hints = get_type_hints(SampledIntradayPrice)
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert hints["observed_at_utc"] is datetime
    assert get_args(hints["sampling_minutes"]) == (5, 10, 15)
    assert get_args(hints["role"]) == (
        "session_open",
        "regular_interval_close",
        "closing_auction_close",
    )
    assert hints["price"] is float
    assert get_args(hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert hints["algorithm_version"] is str
