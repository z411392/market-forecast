from datetime import date, datetime
from typing import get_args, get_type_hints

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.dtos.aggregated_intraday_bar import AggregatedIntradayBar
from libs.realized_variance.dtos.daily_realized_measures import DailyRealizedMeasures
from libs.realized_variance.dtos.intraday_realized_measures import IntradayRealizedMeasures
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)
from pytest import mark


@mark.contract
def test_realized_variance_contract() -> None:
    assert AggregatedIntradayBar.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "bar_start_utc",
            "interval_minutes",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "price_basis",
            "source_minute_count",
        }
    )
    bar_hints = get_type_hints(AggregatedIntradayBar)
    assert bar_hints["security"] is SecurityIdentity
    assert bar_hints["session_date"] is date
    assert bar_hints["bar_start_utc"] is datetime
    assert get_args(bar_hints["interval_minutes"]) == (5, 10, 15)
    assert bar_hints["open"] is float
    assert bar_hints["high"] is float
    assert bar_hints["low"] is float
    assert bar_hints["close"] is float
    assert bar_hints["volume"] is float
    assert get_args(bar_hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert bar_hints["source_minute_count"] is int

    assert IntradayRealizedMeasures.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "sampling_minutes",
            "observation_count",
            "realized_variance",
            "realized_quarticity",
            "positive_semivariance",
            "negative_semivariance",
        }
    )
    intraday_hints = get_type_hints(IntradayRealizedMeasures)
    assert intraday_hints["security"] is SecurityIdentity
    assert intraday_hints["session_date"] is date
    assert get_args(intraday_hints["sampling_minutes"]) == (5, 10, 15)
    assert intraday_hints["observation_count"] is int
    assert intraday_hints["realized_variance"] is float
    assert intraday_hints["realized_quarticity"] is float
    assert intraday_hints["positive_semivariance"] is float
    assert intraday_hints["negative_semivariance"] is float

    assert DailyRealizedMeasures.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "sampling_minutes",
            "regular_session_variance",
            "overnight_log_return",
            "overnight_variance",
            "whole_day_variance",
            "regular_positive_semivariance",
            "regular_negative_semivariance",
            "whole_day_positive_semivariance",
            "whole_day_negative_semivariance",
            "realized_quarticity",
            "observation_count",
        }
    )
    daily_hints = get_type_hints(DailyRealizedMeasures)
    assert daily_hints["security"] is SecurityIdentity
    assert daily_hints["session_date"] is date
    assert get_args(daily_hints["sampling_minutes"]) == (5, 10, 15)
    for field in (
        "regular_session_variance",
        "overnight_log_return",
        "overnight_variance",
        "whole_day_variance",
        "regular_positive_semivariance",
        "regular_negative_semivariance",
        "whole_day_positive_semivariance",
        "whole_day_negative_semivariance",
        "realized_quarticity",
    ):
        assert daily_hints[field] is float
    assert daily_hints["observation_count"] is int

    assert issubclass(InvalidRealizedVarianceInputError, ValueError)
    assert InvalidRealizedVarianceInputError.type == "invalid_realized_variance_input"
