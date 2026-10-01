from datetime import datetime, timedelta
from math import isclose, isfinite, log

from libs.market_data.dtos.session_open_price_observation import SessionOpenPriceObservation
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
    session_open: SessionOpenPriceObservation,
) -> IntradayRealizedMeasures:
    if not samples:
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
    if first["role"] != "regular_interval_close":
        raise InvalidRealizedVarianceInputError("invalid_first_sample_role")
    if samples[-1]["role"] != "closing_auction_close":
        raise InvalidRealizedVarianceInputError("missing_closing_auction_sample")

    if session_open["security"] != security:
        raise InvalidRealizedVarianceInputError("session_open_security_mismatch")
    if session_open["session_date"] != session_date:
        raise InvalidRealizedVarianceInputError("session_open_session_mismatch")
    if session_open["price_basis"] != price_basis:
        raise InvalidRealizedVarianceInputError("session_open_price_basis_mismatch")
    if not _is_utc_datetime(session_open["source_interval_start_utc"]):
        raise InvalidRealizedVarianceInputError("session_open_source_time_not_utc")
    if not isfinite(session_open["price"]) or session_open["price"] <= 0.0:
        raise InvalidRealizedVarianceInputError("invalid_session_open_price")

    expected_step = timedelta(minutes=sampling_minutes)
    first_sample_at = first["observed_at_utc"]
    if (
        session_open["source_interval_start_utc"] >= first_sample_at
        or first_sample_at - session_open["source_interval_start_utc"] > expected_step
    ):
        raise InvalidRealizedVarianceInputError("session_open_outside_first_sampling_bucket")

    returns: list[float] = []
    previous_price = session_open["price"]
    previous_sample: SampledIntradayPrice | None = None

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

        if index < len(samples) - 1 and sample["role"] != "regular_interval_close":
            raise InvalidRealizedVarianceInputError("invalid_regular_sample_role")
        if previous_sample is not None:
            if sample["observed_at_utc"] - previous_sample["observed_at_utc"] != expected_step:
                raise InvalidRealizedVarianceInputError("non_uniform_sampling_grid")

        bucket_start = (
            sample["observed_at_utc"] - expected_step
            if previous_sample is None
            else previous_sample["observed_at_utc"]
        )
        _validate_sample_provenance(
            sample,
            bucket_start,
            previous_sample,
        )

        returns.append(log(sample["price"] / previous_price))
        previous_price = sample["price"]
        previous_sample = sample

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


def _validate_sample_provenance(
    sample: SampledIntradayPrice,
    bucket_start: datetime,
    previous_sample: SampledIntradayPrice | None,
) -> None:
    source_start = sample["source_interval_start_utc"]
    source_end = sample["source_interval_end_utc"]
    observed_at = sample["observed_at_utc"]

    if not _is_utc_datetime(source_start) or not _is_utc_datetime(source_end):
        raise InvalidRealizedVarianceInputError("sample_source_time_not_utc")

    lower = sample["staleness_lower_bound_seconds"]
    upper = sample["staleness_upper_bound_seconds"]
    if not isfinite(lower) or not isfinite(upper) or lower < 0.0 or upper < lower:
        raise InvalidRealizedVarianceInputError("invalid_sample_staleness_bounds")

    if sample["role"] == "closing_auction_close":
        if sample["observation_mode"] != "closing_auction":
            raise InvalidRealizedVarianceInputError("invalid_closing_auction_provenance")
        if source_start != observed_at or source_end != observed_at:
            raise InvalidRealizedVarianceInputError("invalid_closing_auction_source_time")
        if lower != 0.0 or upper != 0.0:
            raise InvalidRealizedVarianceInputError("invalid_closing_auction_staleness")
        return

    if sample["observation_mode"] == "closing_auction":
        raise InvalidRealizedVarianceInputError("closing_auction_mode_on_regular_sample")
    if source_end - source_start != timedelta(minutes=1):
        raise InvalidRealizedVarianceInputError("invalid_regular_source_interval")
    if source_end > observed_at:
        raise InvalidRealizedVarianceInputError("sample_source_after_sampling_boundary")

    expected_lower = (observed_at - source_end).total_seconds()
    expected_upper = (observed_at - source_start).total_seconds()
    if not isclose(lower, expected_lower, rel_tol=0.0, abs_tol=1e-9):
        raise InvalidRealizedVarianceInputError("incorrect_staleness_lower_bound")
    if not isclose(upper, expected_upper, rel_tol=0.0, abs_tol=1e-9):
        raise InvalidRealizedVarianceInputError("incorrect_staleness_upper_bound")

    if sample["observation_mode"] == "observed_bucket_close":
        if source_start < bucket_start or source_start >= observed_at:
            raise InvalidRealizedVarianceInputError("observed_source_outside_sampling_bucket")
        return

    if sample["observation_mode"] != "previous_tick":
        raise InvalidRealizedVarianceInputError("unsupported_sample_observation_mode")
    if previous_sample is None:
        raise InvalidRealizedVarianceInputError("previous_tick_on_first_sample")
    if source_end > bucket_start:
        raise InvalidRealizedVarianceInputError("previous_tick_source_inside_sampling_bucket")
    if (
        source_start != previous_sample["source_interval_start_utc"]
        or source_end != previous_sample["source_interval_end_utc"]
        or not isclose(
            sample["price"],
            previous_sample["price"],
            rel_tol=1e-12,
            abs_tol=1e-15,
        )
    ):
        raise InvalidRealizedVarianceInputError("previous_tick_source_discontinuity")


def _is_utc_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)
