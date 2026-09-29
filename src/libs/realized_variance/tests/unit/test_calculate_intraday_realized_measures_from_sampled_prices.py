from datetime import date, datetime, timedelta, timezone
from math import log

from pytest import approx, mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.session_open_price_observation import SessionOpenPriceObservation
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.calculate_intraday_realized_measures_from_sampled_prices import (
    calculate_intraday_realized_measures_from_sampled_prices,
)
from libs.realized_variance.dtos.sampled_intraday_price import SampledIntradayPrice
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _session_open(
    source_interval_start_utc: datetime | None = None,
    price: float = 100.0,
) -> SessionOpenPriceObservation:
    return {
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "source_interval_start_utc": source_interval_start_utc
        or datetime(2026, 9, 24, 1, 2, tzinfo=timezone.utc),
        "price": price,
        "price_basis": "as_printed",
    }


def _sample(
    index: int,
    price: float,
    role: str,
    *,
    observation_mode: str = "observed_bucket_close",
    source_interval_start_utc: datetime | None = None,
) -> SampledIntradayPrice:
    observed_at = (
        datetime(2026, 9, 24, 1, 5, tzinfo=timezone.utc)
        + timedelta(minutes=5 * index)
    )
    if role == "closing_auction_close":
        source_start = observed_at
        source_end = observed_at
        lower = 0.0
        upper = 0.0
        mode = "closing_auction"
    else:
        source_start = source_interval_start_utc or (observed_at - timedelta(minutes=1))
        source_end = source_start + timedelta(minutes=1)
        lower = (observed_at - source_end).total_seconds()
        upper = (observed_at - source_start).total_seconds()
        mode = observation_mode

    return {
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "observed_at_utc": observed_at,
        "sampling_minutes": 5,
        "role": role,
        "price": price,
        "price_basis": "as_printed",
        "source_interval_start_utc": source_start,
        "source_interval_end_utc": source_end,
        "observation_mode": mode,
        "staleness_lower_bound_seconds": lower,
        "staleness_upper_bound_seconds": upper,
        "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
    }


@mark.unit
def test_calculate_intraday_realized_measures_from_sampled_prices() -> None:
    samples = (
        _sample(0, 110.0, "regular_interval_close"),
        _sample(1, 99.0, "regular_interval_close"),
        _sample(2, 108.9, "closing_auction_close"),
    )

    result = calculate_intraday_realized_measures_from_sampled_prices(
        samples,
        _session_open(),
    )

    r0 = log(1.1)
    r1 = log(0.9)
    r2 = log(1.1)
    expected_rv = r0 * r0 + r1 * r1 + r2 * r2

    assert result["security"] == _security()
    assert result["session_date"] == date(2026, 9, 24)
    assert result["sampling_minutes"] == 5
    assert result["price_basis"] == "as_printed"
    assert result["observation_count"] == 3
    assert result["realized_variance"] == approx(expected_rv)
    assert result["realized_quarticity"] == approx(r0**4 + r1**4 + r2**4)
    assert result["positive_semivariance"] == approx(r0 * r0 + r2 * r2)
    assert result["negative_semivariance"] == approx(r1 * r1)
    assert result["algorithm_version"] == XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION

    carried_samples = (
        _sample(0, 110.0, "regular_interval_close"),
        _sample(
            1,
            110.0,
            "regular_interval_close",
            observation_mode="previous_tick",
            source_interval_start_utc=datetime(
                2026,
                9,
                24,
                1,
                4,
                tzinfo=timezone.utc,
            ),
        ),
        _sample(2, 108.9, "closing_auction_close"),
    )
    carried = calculate_intraday_realized_measures_from_sampled_prices(
        carried_samples,
        _session_open(),
    )
    assert carried["observation_count"] == 3

    gapped = list(samples)
    gapped[1] = {
        **gapped[1],
        "observed_at_utc": gapped[1]["observed_at_utc"] + timedelta(minutes=5),
    }
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            tuple(gapped),
            _session_open(),
        )

    wrong_first_role = list(samples)
    wrong_first_role[0] = {**wrong_first_role[0], "role": "closing_auction_close"}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            tuple(wrong_first_role),
            _session_open(),
        )

    open_outside_first_bucket = _session_open(
        source_interval_start_utc=samples[0]["observed_at_utc"],
    )
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            samples,
            open_outside_first_bucket,
        )

    mismatched_open = {
        **_session_open(),
        "price_basis": "split_adjusted",
    }
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            samples,
            mismatched_open,
        )

    invalid_previous_tick = list(carried_samples)
    invalid_previous_tick[1] = {
        **invalid_previous_tick[1],
        "source_interval_start_utc": datetime(
            2026,
            9,
            24,
            1,
            6,
            tzinfo=timezone.utc,
        ),
        "source_interval_end_utc": datetime(
            2026,
            9,
            24,
            1,
            7,
            tzinfo=timezone.utc,
        ),
        "staleness_lower_bound_seconds": 180.0,
        "staleness_upper_bound_seconds": 240.0,
    }
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            tuple(invalid_previous_tick),
            _session_open(),
        )

    invalid_staleness = list(samples)
    invalid_staleness[1] = {
        **invalid_staleness[1],
        "staleness_lower_bound_seconds": 999.0,
    }
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            tuple(invalid_staleness),
            _session_open(),
        )

    non_positive_open = _session_open(price=0.0)
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            samples,
            non_positive_open,
        )

    non_positive = list(samples)
    non_positive[1] = {**non_positive[1], "price": 0.0}
    with raises(InvalidRealizedVarianceInputError):
        calculate_intraday_realized_measures_from_sampled_prices(
            tuple(non_positive),
            _session_open(),
        )
