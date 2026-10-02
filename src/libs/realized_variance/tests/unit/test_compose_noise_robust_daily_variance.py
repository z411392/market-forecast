from datetime import date
from math import log

from pytest import approx, mark, raises

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.taiwan_realized_kernel_estimator_version import (
    TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION,
)
from libs.realized_variance.domain.services.compose_noise_robust_daily_variance import (
    compose_noise_robust_daily_variance,
)
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


@mark.unit
def test_compose_noise_robust_daily_variance() -> None:
    result = compose_noise_robust_daily_variance(
        security=_security(),
        session_date=date(2026, 9, 24),
        price_basis="as_printed",
        previous_closing_price=100.0,
        current_opening_price=110.0,
        intraday_realized_kernel=0.02,
        tick_count=1000,
        return_count=997,
        bandwidth=29,
        noise_variance=0.001,
        sparse_realized_variance=0.015,
    )

    overnight_return = log(1.1)
    overnight_variance = overnight_return * overnight_return

    assert result["security"] == _security()
    assert result["session_date"] == date(2026, 9, 24)
    assert result["price_basis"] == "as_printed"
    assert result["intraday_realized_kernel"] == approx(0.02)
    assert result["overnight_return"] == approx(overnight_return)
    assert result["overnight_variance"] == approx(overnight_variance)
    assert result["whole_day_variance"] == approx(0.02 + overnight_variance)
    assert result["tick_count"] == 1000
    assert result["return_count"] == 997
    assert result["bandwidth"] == 29
    assert result["noise_variance"] == approx(0.001)
    assert result["sparse_realized_variance"] == approx(0.015)
    assert result["estimator_version"] == TAIWAN_REALIZED_KERNEL_ESTIMATOR_VERSION

    zero_intraday = compose_noise_robust_daily_variance(
        security=_security(),
        session_date=date(2026, 9, 24),
        price_basis="as_printed",
        previous_closing_price=100.0,
        current_opening_price=110.0,
        intraday_realized_kernel=0.0,
        tick_count=1000,
        return_count=997,
        bandwidth=1,
        noise_variance=0.0,
        sparse_realized_variance=0.0,
    )
    assert zero_intraday["intraday_realized_kernel"] == approx(0.0)
    assert zero_intraday["sparse_realized_variance"] == approx(0.0)
    assert zero_intraday["whole_day_variance"] == approx(overnight_variance)

    with raises(InvalidRealizedVarianceInputError):
        compose_noise_robust_daily_variance(
            security=_security(),
            session_date=date(2026, 9, 24),
            price_basis="as_printed",
            previous_closing_price=0.0,
            current_opening_price=110.0,
            intraday_realized_kernel=0.02,
            tick_count=1000,
            return_count=997,
            bandwidth=29,
            noise_variance=0.001,
            sparse_realized_variance=0.015,
        )

    with raises(InvalidRealizedVarianceInputError):
        compose_noise_robust_daily_variance(
            security=_security(),
            session_date=date(2026, 9, 24),
            price_basis="as_printed",
            previous_closing_price=100.0,
            current_opening_price=110.0,
            intraday_realized_kernel=-0.01,
            tick_count=1000,
            return_count=997,
            bandwidth=29,
            noise_variance=0.001,
            sparse_realized_variance=0.015,
        )

    with raises(InvalidRealizedVarianceInputError):
        compose_noise_robust_daily_variance(
            security=_security(),
            session_date=date(2026, 9, 24),
            price_basis="as_printed",
            previous_closing_price=100.0,
            current_opening_price=110.0,
            intraday_realized_kernel=0.02,
            tick_count=1,
            return_count=0,
            bandwidth=1,
            noise_variance=0.001,
            sparse_realized_variance=0.015,
        )

    with raises(InvalidRealizedVarianceInputError):
        compose_noise_robust_daily_variance(
            security=_security(),
            session_date=date(2026, 9, 24),
            price_basis="as_printed",
            previous_closing_price=100.0,
            current_opening_price=110.0,
            intraday_realized_kernel=0.02,
            tick_count=1000,
            return_count=10,
            bandwidth=10,
            noise_variance=0.001,
            sparse_realized_variance=0.015,
        )

    with raises(InvalidRealizedVarianceInputError):
        compose_noise_robust_daily_variance(
            security=_security(),
            session_date=date(2026, 9, 24),
            price_basis="as_printed",
            previous_closing_price=100.0,
            current_opening_price=110.0,
            intraday_realized_kernel=0.02,
            tick_count=1000,
            return_count=997,
            bandwidth=29,
            noise_variance=-0.001,
            sparse_realized_variance=0.015,
        )

    with raises(InvalidRealizedVarianceInputError):
        compose_noise_robust_daily_variance(
            security=_security(),
            session_date=date(2026, 9, 24),
            price_basis="as_printed",
            previous_closing_price=100.0,
            current_opening_price=110.0,
            intraday_realized_kernel=0.02,
            tick_count=1000,
            return_count=997,
            bandwidth=29,
            noise_variance=0.001,
            sparse_realized_variance=0.0,
        )
