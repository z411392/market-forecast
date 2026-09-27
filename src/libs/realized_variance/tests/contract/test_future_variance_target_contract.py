from datetime import date
from typing import get_args, get_type_hints

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.dtos.future_variance_target import FutureVarianceTarget
from pytest import mark


@mark.contract
def test_future_variance_target_contract() -> None:
    assert FutureVarianceTarget.__required_keys__ == frozenset(
        {
            "security",
            "sampling_minutes",
            "price_basis",
            "algorithm_version",
            "origin_session_date",
            "horizon_sessions",
            "first_target_session_date",
            "last_target_session_date",
            "average_whole_day_variance",
            "realized_session_count",
            "target_version",
        }
    )
    hints = get_type_hints(FutureVarianceTarget)
    assert hints["security"] is SecurityIdentity
    assert get_args(hints["sampling_minutes"]) == (5, 10, 15)
    assert get_args(hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert hints["algorithm_version"] is str
    assert hints["origin_session_date"] is date
    assert get_args(hints["horizon_sessions"]) == (5, 20)
    assert hints["first_target_session_date"] is date
    assert hints["last_target_session_date"] is date
    assert hints["average_whole_day_variance"] is float
    assert hints["realized_session_count"] is int
    assert get_args(hints["target_version"]) == ("whole_day_variance_v1",)
