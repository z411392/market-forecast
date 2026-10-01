from datetime import date, timedelta
from math import inf, nan
from typing import Literal

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.realized_variance_algorithm_version import (
    REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.build_future_variance_targets import (
    build_future_variance_targets,
)
from libs.realized_variance.dtos.daily_realized_measures import DailyRealizedMeasures
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)
from pytest import approx, mark, raises


def _security(symbol: str = "TEST") -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XNYS",
        "timezone": "America/New_York",
        "calendar_id": "XNYS",
    }


def _daily(
    session_date: date,
    variance: float,
    *,
    symbol: str = "TEST",
    sampling_minutes: Literal[5, 10, 15] = 5,
    price_basis: Literal["as_printed", "split_adjusted"] = "as_printed",
    algorithm_version: str = REALIZED_VARIANCE_ALGORITHM_VERSION,
) -> DailyRealizedMeasures:
    return {
        "security": _security(symbol),
        "session_date": session_date,
        "sampling_minutes": sampling_minutes,
        "price_basis": price_basis,
        "regular_session_variance": variance,
        "overnight_log_return": 0.0,
        "overnight_variance": 0.0,
        "whole_day_variance": variance,
        "regular_positive_semivariance": variance,
        "regular_negative_semivariance": 0.0,
        "whole_day_positive_semivariance": variance,
        "whole_day_negative_semivariance": 0.0,
        "realized_quarticity": variance * variance,
        "observation_count": 10,
        "algorithm_version": algorithm_version,
    }


@mark.unit
def test_build_future_variance_targets() -> None:
    start = date(2026, 1, 1)
    dates_7 = tuple(start + timedelta(days=index) for index in range(7))
    measurements_7 = tuple(
        _daily(session_date, float(index + 1)) for index, session_date in enumerate(dates_7)
    )

    targets_5 = build_future_variance_targets(measurements_7, dates_7, 5)

    assert len(targets_5) == 2
    assert targets_5[0]["security"] == _security()
    assert targets_5[0]["sampling_minutes"] == 5
    assert targets_5[0]["price_basis"] == "as_printed"
    assert targets_5[0]["algorithm_version"] == REALIZED_VARIANCE_ALGORITHM_VERSION
    assert targets_5[0]["origin_session_date"] == dates_7[0]
    assert targets_5[0]["first_target_session_date"] == dates_7[1]
    assert targets_5[0]["last_target_session_date"] == dates_7[5]
    assert targets_5[0]["average_whole_day_variance"] == approx(4.0)
    assert targets_5[0]["realized_session_count"] == 5
    assert targets_5[0]["target_version"] == "whole_day_variance_v1"

    assert targets_5[1]["origin_session_date"] == dates_7[1]
    assert targets_5[1]["first_target_session_date"] == dates_7[2]
    assert targets_5[1]["last_target_session_date"] == dates_7[6]
    assert targets_5[1]["average_whole_day_variance"] == approx(5.0)

    dates_21 = tuple(start + timedelta(days=index) for index in range(21))
    measurements_21 = tuple(
        _daily(session_date, float(index + 1)) for index, session_date in enumerate(dates_21)
    )

    targets_20 = build_future_variance_targets(measurements_21, dates_21, 20)

    assert len(targets_20) == 1
    assert targets_20[0]["origin_session_date"] == dates_21[0]
    assert targets_20[0]["first_target_session_date"] == dates_21[1]
    assert targets_20[0]["last_target_session_date"] == dates_21[20]
    assert targets_20[0]["average_whole_day_variance"] == approx(11.5)
    assert targets_20[0]["realized_session_count"] == 20
    assert targets_20[0]["algorithm_version"] == REALIZED_VARIANCE_ALGORITHM_VERSION
    assert targets_20[0]["target_version"] == "whole_day_variance_v1"

    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(measurements_7, dates_7[:-1], 5)

    mismatched_date_measurements = list(measurements_7)
    mismatched_date_measurements[2] = _daily(dates_7[3], 3.0)
    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(tuple(mismatched_date_measurements), dates_7, 5)

    duplicate_dates = list(dates_7)
    duplicate_dates[2] = duplicate_dates[1]
    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(measurements_7, tuple(duplicate_dates), 5)

    descending_dates = list(dates_7)
    descending_dates[1], descending_dates[2] = descending_dates[2], descending_dates[1]
    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(measurements_7, tuple(descending_dates), 5)

    mixed_security = list(measurements_7)
    mixed_security[2] = _daily(dates_7[2], 3.0, symbol="OTHER")
    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(tuple(mixed_security), dates_7, 5)

    mixed_sampling = list(measurements_7)
    mixed_sampling[2] = _daily(dates_7[2], 3.0, sampling_minutes=10)
    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(tuple(mixed_sampling), dates_7, 5)

    mixed_basis = list(measurements_7)
    mixed_basis[2] = _daily(dates_7[2], 3.0, price_basis="split_adjusted")
    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(tuple(mixed_basis), dates_7, 5)

    mixed_algorithm = list(measurements_7)
    mixed_algorithm[2] = _daily(
        dates_7[2],
        3.0,
        algorithm_version="rv-core-v0",
    )
    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(tuple(mixed_algorithm), dates_7, 5)

    with raises(InvalidRealizedVarianceInputError):
        build_future_variance_targets(measurements_7, dates_7, 10)

    for invalid_variance in (-1.0, nan, inf):
        invalid_measurements = list(measurements_7)
        invalid_measurements[2] = _daily(dates_7[2], invalid_variance)
        with raises(InvalidRealizedVarianceInputError):
            build_future_variance_targets(tuple(invalid_measurements), dates_7, 5)
