from datetime import date, datetime, timedelta, timezone
from math import log

from pytest import approx, mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.calculate_intraday_realized_measures_from_sampled_prices import (
    calculate_intraday_realized_measures_from_sampled_prices,
)
from libs.realized_variance.dtos.sampled_intraday_price import SampledIntradayPrice
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _sample(index: int, price: float, role: str) -> SampledIntradayPrice:
    return {
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "observed_at_utc": datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
        + timedelta(minutes=5 * index),
        "sampling_minutes": 5,
        "role": role,
        "price": price,
        "price_basis": "as_printed",
        "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
    }


@mark.unit
def test_calculate_intraday_realized_measures_from_sampled_prices() -> None:
    samples = (
        _sample(0, 100.0, "session_open"),
        _sample(1, 110.0, "regular_interval_close"),
        _sample(2, 99.0, "regular_interval_close"),
        _sample(3, 108.9, "closing_auction_close"),
    )

    result = calculate_intraday_realized_measures_from_sampled_prices(samples)

    r0 = log(1.1)
    r1 = log(0.9)
    r2 = log(1.1)
    expected_rv = r0 * r0 + r1 * r1 + r2 * r2

    assert result["security"] == _security()
    assert result["session_date"] == date(2026, 9, 24)
    assert result["sampling_minutes"] == 5
    assert result["price_basis"] == "as_printed"
    assert result["observation_count"] == 3
    assert result["realized_variance"] == approx(expected_rv)
    assert result["realized_quarticity"] == approx(r0**4 + r1**4 + r2**4)
    assert result["positive_semivariance"] == approx(r0 * r0 + r2 * r2)
    assert result["negative_semivariance"] == approx(r1 * r1)
    assert result["algorithm_version"] == XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION

    gapped = list(samples)
    gapped[2] = {
        **gapped[2],
        "observed_at_utc": gapped[2]["observed_at_utc"] + timedelta(minutes=5),
    }
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(tuple(gapped))

    wrong_first_role = list(samples)
    wrong_first_role[0] = {**wrong_first_role[0], "role": "regular_interval_close"}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(tuple(wrong_first_role))

    non_positive = list(samples)
    non_positive[1] = {**non_positive[1], "price": 0.0}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(tuple(non_positive))
