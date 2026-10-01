from collections.abc import Iterable
from math import exp, isfinite, log, sqrt

from libs.realized_variance.dtos.measurement_audit_row import MeasurementAuditRow
from libs.realized_variance.dtos.measurement_audit_summary import MeasurementAuditSummary
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def summarize_measurement_audit(
    rows: Iterable[MeasurementAuditRow],
) -> MeasurementAuditSummary:
    items = tuple(rows)
    if len(items) < 2:
        raise InvalidRealizedVarianceInputError(
            "measurement audit summary requires at least two observations"
        )

    expected_security = items[0]["security"]
    expected_price_basis = items[0]["price_basis"]
    expected_algorithm_version = items[0]["algorithm_version"]
    expected_audit_version = items[0]["audit_version"]
    if expected_audit_version != "rv_measurement_audit_v1":
        raise InvalidRealizedVarianceInputError("unsupported measurement audit version")

    variance_5m: list[float] = []
    variance_10m: list[float] = []
    variance_15m: list[float] = []

    for row in items:
        if row["security"] != expected_security:
            raise InvalidRealizedVarianceInputError("mixed security identity")
        if row["price_basis"] != expected_price_basis:
            raise InvalidRealizedVarianceInputError("mixed price basis")
        if row["algorithm_version"] != expected_algorithm_version:
            raise InvalidRealizedVarianceInputError("mixed realized-variance algorithm")
        if row["audit_version"] != expected_audit_version:
            raise InvalidRealizedVarianceInputError("mixed measurement audit version")

        values = (
            row["whole_day_variance_5m"],
            row["whole_day_variance_10m"],
            row["whole_day_variance_15m"],
        )
        if any(not isfinite(value) or value <= 0.0 for value in values):
            raise InvalidRealizedVarianceInputError("whole-day variances must be finite and positive")

        variance_5m.append(values[0])
        variance_10m.append(values[1])
        variance_15m.append(values[2])

    log_5m = tuple(log(value) for value in variance_5m)
    log_10m = tuple(log(value) for value in variance_10m)
    log_15m = tuple(log(value) for value in variance_15m)
    log_ratio_5m_10m = tuple(
        value_5m - value_10m for value_5m, value_10m in zip(log_5m, log_10m, strict=True)
    )
    log_ratio_5m_15m = tuple(
        value_5m - value_15m for value_5m, value_15m in zip(log_5m, log_15m, strict=True)
    )

    return {
        "security": expected_security,
        "price_basis": expected_price_basis,
        "algorithm_version": expected_algorithm_version,
        "observation_count": len(items),
        "pearson_log_rv_5m_10m": _pearson(log_5m, log_10m),
        "pearson_log_rv_5m_15m": _pearson(log_5m, log_15m),
        "spearman_rv_5m_10m": _pearson(
            _average_ranks(variance_5m),
            _average_ranks(variance_10m),
        ),
        "spearman_rv_5m_15m": _pearson(
            _average_ranks(variance_5m),
            _average_ranks(variance_15m),
        ),
        "geometric_bias_5m_vs_10m_pct": (exp(_mean(log_ratio_5m_10m)) - 1.0) * 100.0,
        "geometric_bias_5m_vs_15m_pct": (exp(_mean(log_ratio_5m_15m)) - 1.0) * 100.0,
        "mean_abs_log_gap_5m_10m": _mean(tuple(abs(value) for value in log_ratio_5m_10m)),
        "mean_abs_log_gap_5m_15m": _mean(tuple(abs(value) for value in log_ratio_5m_15m)),
        "first_session_date": min(row["session_date"] for row in items),
        "last_session_date": max(row["session_date"] for row in items),
        "audit_version": "rv_measurement_audit_v1",
    }


def _mean(values: tuple[float, ...]) -> float:
    return sum(values) / len(values)


def _pearson(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:
    left_mean = _mean(left)
    right_mean = _mean(right)
    left_centered = tuple(value - left_mean for value in left)
    right_centered = tuple(value - right_mean for value in right)
    denominator = sqrt(
        sum(value * value for value in left_centered) * sum(value * value for value in right_centered)
    )
    if denominator == 0.0:
        raise InvalidRealizedVarianceInputError("correlation is undefined for constant input")

    correlation = (
        sum(
            left_value * right_value
            for left_value, right_value in zip(
                left_centered,
                right_centered,
                strict=True,
            )
        )
        / denominator
    )
    if not isfinite(correlation):
        raise InvalidRealizedVarianceInputError("correlation is not finite")
    return correlation


def _average_ranks(values: list[float]) -> tuple[float, ...]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0

    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1

        average_rank = ((start + 1) + end) / 2.0
        for position in range(start, end):
            ranks[indexed[position][0]] = average_rank
        start = end

    return tuple(ranks)
