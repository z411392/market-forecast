from datetime import datetime, timedelta, timezone
from math import nan

from pytest import approx, mark, raises

from libs.realized_variance.domain.services.estimate_noise_variance_from_subgrids import (
    estimate_noise_variance_from_subgrids,
)
from libs.realized_variance.domain.services.jitter_log_price_endpoints import (
    jitter_log_price_endpoints,
)
from libs.realized_variance.domain.services.parzen_kernel_weight import (
    parzen_kernel_weight,
)
from libs.realized_variance.domain.services.realized_autocovariance import (
    realized_autocovariance,
)
from libs.realized_variance.domain.services.select_noise_subgrid_stride import (
    select_noise_subgrid_stride,
)
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


@mark.unit
def test_realized_kernel_primitives() -> None:
    assert parzen_kernel_weight(0.0) == approx(1.0)
    assert parzen_kernel_weight(0.25) == approx(0.71875)
    assert parzen_kernel_weight(0.5) == approx(0.25)
    assert parzen_kernel_weight(0.75) == approx(0.03125)
    assert parzen_kernel_weight(1.0) == approx(0.0)
    assert parzen_kernel_weight(1.25) == approx(0.0)

    with raises(InvalidRealizedVarianceInputError):
        parzen_kernel_weight(-0.01)
    with raises(InvalidRealizedVarianceInputError):
        parzen_kernel_weight(nan)

    returns = (1.0, 2.0, 3.0)
    assert realized_autocovariance(returns, 0) == approx(14.0)
    assert realized_autocovariance(returns, 1) == approx(8.0)
    assert realized_autocovariance(returns, 2) == approx(3.0)

    with raises(InvalidRealizedVarianceInputError):
        realized_autocovariance(returns, -1)
    with raises(InvalidRealizedVarianceInputError):
        realized_autocovariance(returns, 3)
    with raises(InvalidRealizedVarianceInputError):
        realized_autocovariance((1.0, nan), 0)

    jittered = jitter_log_price_endpoints(
        (0.0, 2.0, 4.0, 6.0, 8.0, 10.0),
        endpoint_jitter_m=2,
    )
    assert jittered == approx((1.0, 4.0, 6.0, 9.0))

    with raises(InvalidRealizedVarianceInputError):
        jitter_log_price_endpoints((0.0, 1.0, 2.0), endpoint_jitter_m=2)
    with raises(InvalidRealizedVarianceInputError):
        jitter_log_price_endpoints(
            (0.0, 1.0, 2.0, 3.0),
            endpoint_jitter_m=1,
        )
    with raises(InvalidRealizedVarianceInputError):
        jitter_log_price_endpoints(
            (0.0, 1.0, nan, 3.0),
            endpoint_jitter_m=2,
        )


@mark.unit
def test_noise_subgrid_stride_and_variance() -> None:
    start = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)

    ten_second_ticks = tuple(start + timedelta(seconds=10 * index) for index in range(31))
    assert (
        select_noise_subgrid_stride(
            ten_second_ticks,
            target_spacing_seconds=120,
        )
        == 12
    )

    half_up_ticks = tuple(start + timedelta(seconds=48 * index) for index in range(6))
    assert (
        select_noise_subgrid_stride(
            half_up_ticks,
            target_spacing_seconds=120,
        )
        == 3
    )

    two_ticks = (start, start + timedelta(seconds=10))
    assert (
        select_noise_subgrid_stride(
            two_ticks,
            target_spacing_seconds=120,
        )
        == 1
    )

    duplicate_timestamp_ticks = (
        start,
        start,
        start + timedelta(seconds=10),
        start + timedelta(seconds=20),
    )
    assert (
        select_noise_subgrid_stride(
            duplicate_timestamp_ticks,
            target_spacing_seconds=10,
        )
        == 2
    )

    with raises(InvalidRealizedVarianceInputError):
        select_noise_subgrid_stride((start,), target_spacing_seconds=120)
    with raises(InvalidRealizedVarianceInputError):
        select_noise_subgrid_stride(
            (start, start - timedelta(seconds=1)),
            target_spacing_seconds=120,
        )
    with raises(InvalidRealizedVarianceInputError):
        select_noise_subgrid_stride(
            (start, start),
            target_spacing_seconds=120,
        )

    log_prices = (0.0, 1.0, 2.0, 4.0, 6.0, 9.0)
    assert estimate_noise_variance_from_subgrids(log_prices, q=2) == approx(6.75)

    assert estimate_noise_variance_from_subgrids(
        (1.0, 1.0, 1.0, 1.0),
        q=2,
    ) == approx(0.0)

    with raises(InvalidRealizedVarianceInputError):
        estimate_noise_variance_from_subgrids(log_prices, q=0)
    with raises(InvalidRealizedVarianceInputError):
        estimate_noise_variance_from_subgrids(log_prices, q=len(log_prices))
    with raises(InvalidRealizedVarianceInputError):
        estimate_noise_variance_from_subgrids((0.0, nan, 1.0), q=1)
