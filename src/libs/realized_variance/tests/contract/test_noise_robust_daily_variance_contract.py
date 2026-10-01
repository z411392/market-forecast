from datetime import date
from typing import get_args, get_type_hints

from pytest import mark

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.dtos.noise_robust_daily_variance import (
    NoiseRobustDailyVariance,
)


@mark.contract
def test_noise_robust_daily_variance_contract() -> None:
    assert NoiseRobustDailyVariance.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "price_basis",
            "intraday_realized_kernel",
            "overnight_return",
            "overnight_variance",
            "whole_day_variance",
            "tick_count",
            "return_count",
            "bandwidth",
            "noise_variance",
            "sparse_realized_variance",
            "estimator_version",
        }
    )

    hints = get_type_hints(NoiseRobustDailyVariance)
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert get_args(hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert hints["intraday_realized_kernel"] is float
    assert hints["overnight_return"] is float
    assert hints["overnight_variance"] is float
    assert hints["whole_day_variance"] is float
    assert hints["tick_count"] is int
    assert hints["return_count"] is int
    assert hints["bandwidth"] is int
    assert hints["noise_variance"] is float
    assert hints["sparse_realized_variance"] is float
    assert hints["estimator_version"] is str
