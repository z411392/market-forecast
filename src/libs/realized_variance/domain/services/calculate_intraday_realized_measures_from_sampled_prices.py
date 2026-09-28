from datetime import datetime, timedelta
from math import isfinite, log

from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.dtos.intraday_realized_measures import IntradayRealizedMeasures
from libs.realized_variance.dtos.sampled_intraday_price import SampledIntradayPrice
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def calculate_intraday_realized_measures_from_sampled_prices(
    samples: tuple[SampledIntradayPrice, ...],
) -> IntradayRealizedMeasures:
    if len(samples) < 2:
        raise InvalidRealizedVarianceInputError("insufficient_sampled_prices")

    first = samples[0]
    security = first["security"]
    session_date = first["session_date"]
    sampling_minutes = first["sampling_minutes"]
    price_basis = first["price_basis"]
    algorithm_version = first["algorithm_version"]

    if sampling_minutes not in (5, 10, 15):
        raise InvalidRealizedVarianceInputError("unsupported_sampling_interval")
    if algorithm_version != XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION:
        raise InvalidRealizedVarianceInputError("unsupported_algorithm_version")
    if first["role"] != "session_open":
        raise InvalidRealizedVarianceInputError("missing_session_open_sample")
    if samples[-1]["role"] != "closing_auction_close":
        raise InvalidRealizedVarianceInputError("missing_closing_auction_sample")

    expected_step = timedelta(minutes=sampling_minutes)
    returns: list[float] = []

    for index, sample in enumerate(samples):
        if sample["security"] != security:
            raise InvalidRealizedVarianceInputError("mixed_security")
        if sample["session_date"] != session_date:
            raise InvalidRealizedVarianceInputError("mixed_session")
        if sample["sampling_minutes"] != sampling_minutes:
            raise InvalidRealizedVarianceInputError("mixed_sampling_interval")
        if sample["price_basis"] != price_basis:
            raise InvalidRealizedVarianceInputError("mixed_price_basis")
        if sample["algorithm_version"] != algorithm_version:
            raise InvalidRealizedVarianceInputError("mixed_algorithm_version")
        if not _is_utc_datetime(sample["observed_at_utc"]):
            raise InvalidRealizedVarianceInputError("sample_time_not_utc")
        if not isfinite(sample["price"]) or sample["price"] <= 0.0:
            raise InvalidRealizedVarianceInputError("non_positive_or_non_finite_price")

        if index == 0:
            continue

        if index < len(samples) - 1 and sample["role"] != "regular_interval_close":
            raise InvalidRealizedVarianceInputError("invalid_regular_sample_role")
        if sample["observed_at_utc"] - samples[index - 1]["observed_at_utc"] != expected_step:
            raise InvalidRealizedVarianceInputError("non_uniform_sampling_grid")

        returns.append(log(sample["price"] / samples[index - 1]["price"]))

    squared = tuple(value * value for value in returns)
    realized_variance = sum(squared)
    realized_quarticity = len(returns) / 3.0 * sum(value * value for value in squared)
    positive_semivariance = sum(
        squared_return
        for interval_return, squared_return in zip(returns, squared, strict=True)
        if interval_return >= 0.0
    )
    negative_semivariance = sum(
        squared_return
        for interval_return, squared_return in zip(returns, squared, strict=True)
        if interval_return < 0.0
    )

    return {
        "security": security,
        "session_date": session_date,
        "sampling_minutes": sampling_minutes,
        "price_basis": price_basis,
        "observation_count": len(returns),
        "realized_variance": realized_variance,
        "realized_quarticity": realized_quarticity,
        "positive_semivariance": positive_semivariance,
        "negative_semivariance": negative_semivariance,
        "algorithm_version": algorithm_version,
    }


def _is_utc_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)
