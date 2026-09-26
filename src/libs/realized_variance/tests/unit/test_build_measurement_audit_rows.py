from datetime import date
from math import inf, log, nan

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.domain.services.build_measurement_audit_rows import (
    build_measurement_audit_rows,
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
    sampling_minutes: int,
    whole_day_variance: float,
    *,
    symbol: str = "TEST",
    price_basis: str = "as_printed",
) -> DailyRealizedMeasures:
    return {
        "security": _security(symbol),
        "session_date": session_date,
        "sampling_minutes": sampling_minutes,
        "price_basis": price_basis,
        "regular_session_variance": whole_day_variance,
        "overnight_log_return": 0.0,
        "overnight_variance": 0.0,
        "whole_day_variance": whole_day_variance,
        "regular_positive_semivariance": whole_day_variance,
        "regular_negative_semivariance": 0.0,
        "whole_day_positive_semivariance": whole_day_variance,
        "whole_day_negative_semivariance": 0.0,
        "realized_quarticity": whole_day_variance * whole_day_variance,
        "observation_count": 10,
    }


@mark.unit
def test_build_measurement_audit_rows() -> None:
    first_date = date(2026, 9, 24)
    second_date = date(2026, 9, 25)

    measurements = (
        _daily(second_date, 15, 18.0),
        _daily(first_date, 10, 2.0),
        _daily(second_date, 5, 9.0),
        _daily(first_date, 5, 4.0),
        _daily(second_date, 10, 3.0),
        _daily(first_date, 15, 1.0),
    )

    rows = build_measurement_audit_rows(measurements)

    assert tuple(row["session_date"] for row in rows) == (first_date, second_date)
    assert rows[0]["security"] == _security()
    assert rows[0]["price_basis"] == "as_printed"
    assert rows[0]["whole_day_variance_5m"] == approx(4.0)
    assert rows[0]["whole_day_variance_10m"] == approx(2.0)
    assert rows[0]["whole_day_variance_15m"] == approx(1.0)
    assert rows[0]["log_ratio_5m_10m"] == approx(log(2.0))
    assert rows[0]["log_ratio_5m_15m"] == approx(log(4.0))
    assert rows[0]["abs_log_gap_5m_10m"] == approx(log(2.0))
    assert rows[0]["abs_log_gap_5m_15m"] == approx(log(4.0))
    assert rows[0]["audit_version"] == "rv_measurement_audit_v1"

    assert rows[1]["whole_day_variance_5m"] == approx(9.0)
    assert rows[1]["whole_day_variance_10m"] == approx(3.0)
    assert rows[1]["whole_day_variance_15m"] == approx(18.0)
    assert rows[1]["log_ratio_5m_10m"] == approx(log(3.0))
    assert rows[1]["log_ratio_5m_15m"] == approx(log(0.5))
    assert rows[1]["abs_log_gap_5m_10m"] == approx(log(3.0))
    assert rows[1]["abs_log_gap_5m_15m"] == approx(log(2.0))

    with raises(InvalidRealizedVarianceInputError):
        build_measurement_audit_rows(
            (
                _daily(first_date, 5, 4.0),
                _daily(first_date, 10, 2.0, symbol="OTHER"),
                _daily(first_date, 15, 1.0),
            )
        )

    with raises(InvalidRealizedVarianceInputError):
        build_measurement_audit_rows(
            (
                _daily(first_date, 5, 4.0),
                _daily(first_date, 10, 2.0, price_basis="split_adjusted"),
                _daily(first_date, 15, 1.0),
            )
        )

    with raises(InvalidRealizedVarianceInputError):
        build_measurement_audit_rows(
            (
                _daily(first_date, 5, 4.0),
                _daily(first_date, 5, 5.0),
                _daily(first_date, 10, 2.0),
                _daily(first_date, 15, 1.0),
            )
        )

    with raises(InvalidRealizedVarianceInputError):
        build_measurement_audit_rows(
            (
                _daily(first_date, 5, 4.0),
                _daily(first_date, 10, 2.0),
            )
        )

    unsupported = {
        **_daily(first_date, 15, 1.0),
        "sampling_minutes": 30,
    }
    with raises(InvalidRealizedVarianceInputError):
        build_measurement_audit_rows(
            (
                _daily(first_date, 5, 4.0),
                _daily(first_date, 10, 2.0),
                unsupported,
            )
        )

    for invalid_variance in (0.0, -1.0, nan, inf):
        with raises(InvalidRealizedVarianceInputError):
            build_measurement_audit_rows(
                (
                    _daily(first_date, 5, invalid_variance),
                    _daily(first_date, 10, 2.0),
                    _daily(first_date, 15, 1.0),
                )
            )
