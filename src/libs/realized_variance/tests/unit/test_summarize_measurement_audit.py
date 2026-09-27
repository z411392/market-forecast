from datetime import date
from math import log
from typing import Literal

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.realized_variance_algorithm_version import (
    REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.summarize_measurement_audit import (
    summarize_measurement_audit,
)
from libs.realized_variance.dtos.measurement_audit_row import MeasurementAuditRow
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


def _row(
    session_date: date,
    variance_5m: float,
    variance_10m: float,
    variance_15m: float,
    *,
    symbol: str = "TEST",
    price_basis: Literal["as_printed", "split_adjusted"] = "as_printed",
    algorithm_version: str = REALIZED_VARIANCE_ALGORITHM_VERSION,
) -> MeasurementAuditRow:
    log_ratio_5m_10m = log(variance_5m / variance_10m)
    log_ratio_5m_15m = log(variance_5m / variance_15m)
    return {
        "security": _security(symbol),
        "session_date": session_date,
        "price_basis": price_basis,
        "algorithm_version": algorithm_version,
        "whole_day_variance_5m": variance_5m,
        "whole_day_variance_10m": variance_10m,
        "whole_day_variance_15m": variance_15m,
        "log_ratio_5m_10m": log_ratio_5m_10m,
        "log_ratio_5m_15m": log_ratio_5m_15m,
        "abs_log_gap_5m_10m": abs(log_ratio_5m_10m),
        "abs_log_gap_5m_15m": abs(log_ratio_5m_15m),
        "audit_version": "rv_measurement_audit_v1",
    }


@mark.unit
def test_summarize_measurement_audit() -> None:
    rows = (
        _row(date(2026, 9, 22), 1.0, 1.0, 0.5),
        _row(date(2026, 9, 23), 1.0, 4.0, 0.5),
        _row(date(2026, 9, 24), 4.0, 1.0, 2.0),
        _row(date(2026, 9, 25), 4.0, 4.0, 2.0),
    )

    summary = summarize_measurement_audit(rows)

    assert summary["security"] == _security()
    assert summary["price_basis"] == "as_printed"
    assert summary["algorithm_version"] == REALIZED_VARIANCE_ALGORITHM_VERSION
    assert summary["observation_count"] == 4
    assert summary["pearson_log_rv_5m_10m"] == approx(0.0, abs=1e-12)
    assert summary["pearson_log_rv_5m_15m"] == approx(1.0)
    assert summary["spearman_rv_5m_10m"] == approx(0.0, abs=1e-12)
    assert summary["spearman_rv_5m_15m"] == approx(1.0)
    assert summary["geometric_bias_5m_vs_10m_pct"] == approx(0.0, abs=1e-12)
    assert summary["geometric_bias_5m_vs_15m_pct"] == approx(100.0)
    assert summary["mean_abs_log_gap_5m_10m"] == approx(log(2.0))
    assert summary["mean_abs_log_gap_5m_15m"] == approx(log(2.0))
    assert summary["first_session_date"] == date(2026, 9, 22)
    assert summary["last_session_date"] == date(2026, 9, 25)
    assert summary["audit_version"] == "rv_measurement_audit_v1"

    with raises(InvalidRealizedVarianceInputError):
        summarize_measurement_audit((rows[0],))

    mixed_security = (
        rows[0],
        {**rows[1], "security": _security("OTHER")},
    )
    with raises(InvalidRealizedVarianceInputError):
        summarize_measurement_audit(mixed_security)

    mixed_basis = (
        rows[0],
        {**rows[1], "price_basis": "split_adjusted"},
    )
    with raises(InvalidRealizedVarianceInputError):
        summarize_measurement_audit(mixed_basis)

    mixed_algorithm = (
        rows[0],
        {**rows[1], "algorithm_version": "rv-core-v0"},
    )
    with raises(InvalidRealizedVarianceInputError):
        summarize_measurement_audit(mixed_algorithm)

    constant = (
        _row(date(2026, 9, 22), 1.0, 1.0, 0.5),
        _row(date(2026, 9, 23), 1.0, 2.0, 1.0),
        _row(date(2026, 9, 24), 1.0, 4.0, 2.0),
    )
    with raises(InvalidRealizedVarianceInputError):
        summarize_measurement_audit(constant)
