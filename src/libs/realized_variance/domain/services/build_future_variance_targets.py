from collections.abc import Iterable
from datetime import date
from math import isfinite
from typing import Literal

from libs.realized_variance.dtos.daily_realized_measures import DailyRealizedMeasures
from libs.realized_variance.dtos.future_variance_target import FutureVarianceTarget
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def build_future_variance_targets(
    measurements: Iterable[DailyRealizedMeasures],
    session_dates: Iterable[date],
    horizon_sessions: Literal[5, 20],
) -> tuple[FutureVarianceTarget, ...]:
    items = tuple(measurements)
    dates = tuple(session_dates)

    if horizon_sessions not in (5, 20):
        raise InvalidRealizedVarianceInputError("unsupported future-variance horizon")
    if len(items) != len(dates):
        raise InvalidRealizedVarianceInputError(
            "measurement and session-date counts must match"
        )
    if any(
        current_date >= next_date
        for current_date, next_date in zip(dates, dates[1:], strict=True)
    ):
        raise InvalidRealizedVarianceInputError(
            "session dates must be strictly increasing"
        )
    if not items:
        return ()

    expected_security = items[0]["security"]
    expected_sampling_minutes = items[0]["sampling_minutes"]
    expected_price_basis = items[0]["price_basis"]
    expected_algorithm_version = items[0]["algorithm_version"]

    for measurement, session_date in zip(items, dates, strict=True):
        if measurement["session_date"] != session_date:
            raise InvalidRealizedVarianceInputError(
                "measurement session date does not match validated session sequence"
            )
        if measurement["security"] != expected_security:
            raise InvalidRealizedVarianceInputError("mixed security identity")
        if measurement["sampling_minutes"] != expected_sampling_minutes:
            raise InvalidRealizedVarianceInputError("mixed sampling interval")
        if measurement["price_basis"] != expected_price_basis:
            raise InvalidRealizedVarianceInputError("mixed price basis")
        if measurement["algorithm_version"] != expected_algorithm_version:
            raise InvalidRealizedVarianceInputError(
                "mixed realized-variance algorithm"
            )

        whole_day_variance = measurement["whole_day_variance"]
        if not isfinite(whole_day_variance) or whole_day_variance < 0.0:
            raise InvalidRealizedVarianceInputError(
                "whole-day variance must be finite and non-negative"
            )

    targets: list[FutureVarianceTarget] = []
    for origin_index in range(len(items) - horizon_sessions):
        first_target_index = origin_index + 1
        last_target_index = origin_index + horizon_sessions
        future_variances = tuple(
            item["whole_day_variance"]
            for item in items[first_target_index : last_target_index + 1]
        )

        targets.append(
            {
                "security": expected_security,
                "sampling_minutes": expected_sampling_minutes,
                "price_basis": expected_price_basis,
                "algorithm_version": expected_algorithm_version,
                "origin_session_date": dates[origin_index],
                "horizon_sessions": horizon_sessions,
                "first_target_session_date": dates[first_target_index],
                "last_target_session_date": dates[last_target_index],
                "average_whole_day_variance": (
                    sum(future_variances) / horizon_sessions
                ),
                "realized_session_count": horizon_sessions,
                "target_version": "whole_day_variance_v1",
            }
        )

    return tuple(targets)
