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
            "source_interval_start_utc",
            "source_interval_end_utc",
            "observation_mode",
            "staleness_lower_bound_seconds",
            "staleness_upper_bound_seconds",
            "algorithm_version",
        }
    )

    hints = get_type_hints(SampledIntradayPrice)
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert hints["observed_at_utc"] is datetime
    assert get_args(hints["sampling_minutes"]) == (5, 10, 15)
    assert get_args(hints["role"]) == (
        "regular_interval_close",
        "closing_auction_close",
    )
    assert hints["price"] is float
    assert get_args(hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert hints["source_interval_start_utc"] is datetime
    assert hints["source_interval_end_utc"] is datetime
    assert get_args(hints["observation_mode"]) == (
        "observed_bucket_close",
        "previous_tick",
        "closing_auction",
    )
    assert hints["staleness_lower_bound_seconds"] is float
    assert hints["staleness_upper_bound_seconds"] is float
    assert hints["algorithm_version"] is str
