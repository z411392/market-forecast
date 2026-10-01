from math import isclose, isfinite

from libs.realized_variance.constants.realized_variance_algorithm_version import (
    REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.dtos.daily_realized_measures import DailyRealizedMeasures
from libs.realized_variance.dtos.intraday_realized_measures import IntradayRealizedMeasures
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def calculate_daily_realized_measures(
    intraday: IntradayRealizedMeasures,
    overnight_log_return: float,
) -> DailyRealizedMeasures:
    if not isfinite(overnight_log_return):
        raise InvalidRealizedVarianceInputError("invalid_overnight_log_return")
    if intraday["algorithm_version"] != REALIZED_VARIANCE_ALGORITHM_VERSION:
        raise InvalidRealizedVarianceInputError("unsupported_algorithm_version")
    if intraday["observation_count"] <= 0:
        raise InvalidRealizedVarianceInputError("invalid_observation_count")

    _require_nonnegative_finite(intraday["realized_variance"])
    _require_nonnegative_finite(intraday["realized_quarticity"])
    _require_nonnegative_finite(intraday["positive_semivariance"])
    _require_nonnegative_finite(intraday["negative_semivariance"])

    semivariance_total = intraday["positive_semivariance"] + intraday["negative_semivariance"]
    if not isclose(
        semivariance_total,
        intraday["realized_variance"],
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise InvalidRealizedVarianceInputError("inconsistent_semivariance_total")

    overnight_variance = overnight_log_return * overnight_log_return
    whole_day_variance = intraday["realized_variance"] + overnight_variance

    whole_day_positive_semivariance = intraday["positive_semivariance"]
    whole_day_negative_semivariance = intraday["negative_semivariance"]

    if overnight_log_return >= 0.0:
        whole_day_positive_semivariance += overnight_variance
    else:
        whole_day_negative_semivariance += overnight_variance

    return {
        "security": intraday["security"],
        "session_date": intraday["session_date"],
        "sampling_minutes": intraday["sampling_minutes"],
        "price_basis": intraday["price_basis"],
        "regular_session_variance": intraday["realized_variance"],
        "overnight_log_return": overnight_log_return,
        "overnight_variance": overnight_variance,
        "whole_day_variance": whole_day_variance,
        "regular_positive_semivariance": intraday["positive_semivariance"],
        "regular_negative_semivariance": intraday["negative_semivariance"],
        "whole_day_positive_semivariance": whole_day_positive_semivariance,
        "whole_day_negative_semivariance": whole_day_negative_semivariance,
        "realized_quarticity": intraday["realized_quarticity"],
        "observation_count": intraday["observation_count"],
        "algorithm_version": intraday["algorithm_version"],
    }


def _require_nonnegative_finite(value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise InvalidRealizedVarianceInputError("invalid_intraday_measure")
