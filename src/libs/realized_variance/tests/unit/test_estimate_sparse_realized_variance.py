from datetime import datetime, timedelta, timezone
from math import nan

from pytest import approx, mark, raises

from libs.realized_variance.domain.services.estimate_sparse_realized_variance import (
    estimate_sparse_realized_variance,
)
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


@mark.unit
def test_estimate_sparse_realized_variance() -> None:
    start = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
    timestamps = (
        start,
        start + timedelta(seconds=1),
        start + timedelta(seconds=3),
        start + timedelta(seconds=4),
    )
    log_prices = (0.0, 1.0, 2.0, 4.0)

    assert estimate_sparse_realized_variance(
        timestamps=timestamps,
        log_prices=log_prices,
        interval_seconds=2,
        phase_shift_seconds=1,
    ) == approx(5.5)

    assert estimate_sparse_realized_variance(
        timestamps=timestamps,
        log_prices=(1.0, 1.0, 1.0, 1.0),
        interval_seconds=2,
        phase_shift_seconds=1,
    ) == approx(0.0)

    duplicate_timestamps = (
        start,
        start,
        start + timedelta(seconds=2),
        start + timedelta(seconds=4),
    )
    assert estimate_sparse_realized_variance(
        timestamps=duplicate_timestamps,
        log_prices=(0.0, 0.5, 1.0, 2.0),
        interval_seconds=2,
        phase_shift_seconds=1,
    ) == approx(0.75)


@mark.unit
def test_estimate_sparse_realized_variance_rejects_invalid_inputs() -> None:
    start = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
    timestamps = (
        start,
        start + timedelta(seconds=1),
        start + timedelta(seconds=3),
        start + timedelta(seconds=4),
    )
    prices = (0.0, 1.0, 2.0, 4.0)

    with raises(InvalidRealizedVarianceInputError):
        estimate_sparse_realized_variance(
            timestamps=timestamps[:-1],
            log_prices=prices,
            interval_seconds=2,
            phase_shift_seconds=1,
        )
    with raises(InvalidRealizedVarianceInputError):
        estimate_sparse_realized_variance(
            timestamps=(timestamps[0], timestamps[2], timestamps[1], timestamps[3]),
            log_prices=prices,
            interval_seconds=2,
            phase_shift_seconds=1,
        )
    with raises(InvalidRealizedVarianceInputError):
        estimate_sparse_realized_variance(
            timestamps=timestamps,
            log_prices=(0.0, 1.0, nan, 4.0),
            interval_seconds=2,
            phase_shift_seconds=1,
        )
    with raises(InvalidRealizedVarianceInputError):
        estimate_sparse_realized_variance(
            timestamps=timestamps,
            log_prices=prices,
            interval_seconds=0,
            phase_shift_seconds=1,
        )
    with raises(InvalidRealizedVarianceInputError):
        estimate_sparse_realized_variance(
            timestamps=timestamps,
            log_prices=prices,
            interval_seconds=2,
            phase_shift_seconds=0,
        )
    with raises(InvalidRealizedVarianceInputError):
        estimate_sparse_realized_variance(
            timestamps=timestamps,
            log_prices=prices,
            interval_seconds=2,
            phase_shift_seconds=3,
        )
