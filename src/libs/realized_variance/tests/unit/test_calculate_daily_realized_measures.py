from datetime import date
from math import nan

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.domain.services.calculate_daily_realized_measures import (
    calculate_daily_realized_measures,
)
from libs.realized_variance.dtos.intraday_realized_measures import IntradayRealizedMeasures
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)
from pytest import approx, mark, raises


def _security() -> SecurityIdentity:
    return {
        "symbol": "TEST",
        "exchange": "XNYS",
        "timezone": "America/New_York",
        "calendar_id": "XNYS",
    }


def _intraday() -> IntradayRealizedMeasures:
    return {
        "security": _security(),
        "session_date": date(2026, 9, 25),
        "sampling_minutes": 5,
        "price_basis": "as_printed",
        "observation_count": 10,
        "realized_variance": 0.04,
        "realized_quarticity": 0.003,
        "positive_semivariance": 0.03,
        "negative_semivariance": 0.01,
    }


@mark.unit
def test_calculate_daily_realized_measures() -> None:
    positive = calculate_daily_realized_measures(_intraday(), 0.1)
    assert positive["security"] == _security()
    assert positive["session_date"] == date(2026, 9, 25)
    assert positive["sampling_minutes"] == 5
    assert positive["price_basis"] == "as_printed"
    assert positive["regular_session_variance"] == approx(0.04)
    assert positive["overnight_log_return"] == approx(0.1)
    assert positive["overnight_variance"] == approx(0.01)
    assert positive["whole_day_variance"] == approx(0.05)
    assert positive["regular_positive_semivariance"] == approx(0.03)
    assert positive["regular_negative_semivariance"] == approx(0.01)
    assert positive["whole_day_positive_semivariance"] == approx(0.04)
    assert positive["whole_day_negative_semivariance"] == approx(0.01)
    assert positive["realized_quarticity"] == approx(0.003)
    assert positive["observation_count"] == 10

    negative = calculate_daily_realized_measures(_intraday(), -0.1)
    assert negative["whole_day_positive_semivariance"] == approx(0.03)
    assert negative["whole_day_negative_semivariance"] == approx(0.02)

    inconsistent = {**_intraday(), "positive_semivariance": 0.02}
    with raises(InvalidRealizedVarianceInputError):
        calculate_daily_realized_measures(inconsistent, 0.1)

    with raises(InvalidRealizedVarianceInputError):
        calculate_daily_realized_measures(_intraday(), nan)
