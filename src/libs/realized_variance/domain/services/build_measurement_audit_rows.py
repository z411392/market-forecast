from collections.abc import Iterable
from datetime import date
from math import isfinite, log

from libs.realized_variance.dtos.daily_realized_measures import DailyRealizedMeasures
from libs.realized_variance.dtos.measurement_audit_row import MeasurementAuditRow
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def build_measurement_audit_rows(
    measurements: Iterable[DailyRealizedMeasures],
) -> tuple[MeasurementAuditRow, ...]:
    items = tuple(measurements)
    if not items:
        raise InvalidRealizedVarianceInputError("measurement audit input is empty")

    expected_security = items[0]["security"]
    expected_price_basis = items[0]["price_basis"]
    expected_algorithm_version = items[0]["algorithm_version"]
    by_session: dict[date, dict[int, DailyRealizedMeasures]] = {}

    for measurement in items:
        if measurement["security"] != expected_security:
            raise InvalidRealizedVarianceInputError("mixed security identity")
        if measurement["price_basis"] != expected_price_basis:
            raise InvalidRealizedVarianceInputError("mixed price basis")
        if measurement["algorithm_version"] != expected_algorithm_version:
            raise InvalidRealizedVarianceInputError("mixed realized-variance algorithm")

        sampling_minutes = measurement["sampling_minutes"]
        if sampling_minutes not in (5, 10, 15):
            raise InvalidRealizedVarianceInputError("unsupported sampling interval")

        whole_day_variance = measurement["whole_day_variance"]
        if not isfinite(whole_day_variance) or whole_day_variance <= 0.0:
            raise InvalidRealizedVarianceInputError("whole-day variance must be finite and positive")

        session_rows = by_session.setdefault(measurement["session_date"], {})
        if sampling_minutes in session_rows:
            raise InvalidRealizedVarianceInputError("duplicate sampling interval for session")
        session_rows[sampling_minutes] = measurement

    rows: list[MeasurementAuditRow] = []
    for session_date in sorted(by_session):
        session_rows = by_session[session_date]
        if set(session_rows) != {5, 10, 15}:
            raise InvalidRealizedVarianceInputError("session requires 5m, 10m, and 15m measurements")

        variance_5m = session_rows[5]["whole_day_variance"]
        variance_10m = session_rows[10]["whole_day_variance"]
        variance_15m = session_rows[15]["whole_day_variance"]
        log_ratio_5m_10m = log(variance_5m / variance_10m)
        log_ratio_5m_15m = log(variance_5m / variance_15m)

        rows.append(
            {
                "security": expected_security,
                "session_date": session_date,
                "price_basis": expected_price_basis,
                "algorithm_version": expected_algorithm_version,
                "whole_day_variance_5m": variance_5m,
                "whole_day_variance_10m": variance_10m,
                "whole_day_variance_15m": variance_15m,
                "log_ratio_5m_10m": log_ratio_5m_10m,
                "log_ratio_5m_15m": log_ratio_5m_15m,
                "abs_log_gap_5m_10m": abs(log_ratio_5m_10m),
                "abs_log_gap_5m_15m": abs(log_ratio_5m_15m),
                "audit_version": "rv_measurement_audit_v1",
            }
        )

    return tuple(rows)
