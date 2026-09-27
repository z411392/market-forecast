from datetime import date, datetime, timedelta, timezone
from math import log

from pytest import approx, mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.realized_variance_algorithm_version import (
    REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.calculate_intraday_realized_measures import (
    calculate_intraday_realized_measures,
)
from libs.realized_variance.dtos.aggregated_intraday_bar import AggregatedIntradayBar
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "TEST",
        "exchange": "XNYS",
        "timezone": "America/New_York",
        "calendar_id": "XNYS",
    }


def _bar(start: datetime, index: int, opening: float, close: float) -> AggregatedIntradayBar:
    return {
        "security": _security(),
        "session_date": date(2026, 9, 25),
        "bar_start_utc": start + timedelta(minutes=5 * index),
        "interval_minutes": 5,
        "open": opening,
        "high": max(opening, close),
        "low": min(opening, close),
        "close": close,
        "volume": 1000.0,
        "price_basis": "as_printed",
        "source_minute_count": 5,
        "algorithm_version": REALIZED_VARIANCE_ALGORITHM_VERSION,
    }


@mark.unit
def test_calculate_intraday_realized_measures() -> None:
    start = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)
    bars = (
        _bar(start, 0, 100.0, 110.0),
        _bar(start, 1, 110.0, 99.0),
        _bar(start, 2, 99.0, 108.9),
    )

    result = calculate_intraday_realized_measures(bars)

    r0 = log(1.1)
    r1 = log(0.9)
    r2 = log(1.1)
    expected_rv = r0 * r0 + r1 * r1 + r2 * r2
    expected_rq = r0**4 + r1**4 + r2**4
    expected_positive = r0 * r0 + r2 * r2
    expected_negative = r1 * r1

    assert result["security"] == _security()
    assert result["session_date"] == date(2026, 9, 25)
    assert result["sampling_minutes"] == 5
    assert result["price_basis"] == "as_printed"
    assert result["algorithm_version"] == REALIZED_VARIANCE_ALGORITHM_VERSION
    assert result["observation_count"] == 3
    assert result["realized_variance"] == approx(expected_rv)
    assert result["realized_quarticity"] == approx(expected_rq)
    assert result["positive_semivariance"] == approx(expected_positive)
    assert result["negative_semivariance"] == approx(expected_negative)
    assert (
        result["positive_semivariance"] + result["negative_semivariance"]
        == approx(result["realized_variance"])
    )

    mixed_sampling = list(bars)
    mixed_sampling[1] = {**mixed_sampling[1], "interval_minutes": 10, "source_minute_count": 10}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures(tuple(mixed_sampling))

    mixed_session = list(bars)
    mixed_session[1] = {**mixed_session[1], "session_date": date(2026, 9, 26)}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures(tuple(mixed_session))

    mixed_basis = list(bars)
    mixed_basis[1] = {**mixed_basis[1], "price_basis": "split_adjusted"}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures(tuple(mixed_basis))

    unsupported_version = list(bars)
    unsupported_version[1] = {**unsupported_version[1], "algorithm_version": "rv-core-v2"}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures(tuple(unsupported_version))

    gapped = list(bars)
    gapped[1] = {**gapped[1], "bar_start_utc": start + timedelta(minutes=10)}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures(tuple(gapped))

    non_positive = list(bars)
    non_positive[1] = {**non_positive[1], "close": 0.0}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures(tuple(non_positive))
