from datetime import date

from pytest import mark

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.calculate_daily_realized_measures import (
    calculate_daily_realized_measures,
)
from libs.realized_variance.dtos.intraday_realized_measures import IntradayRealizedMeasures


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


@mark.unit
def test_calculate_daily_realized_measures_accepts_xtai_algorithm_version() -> None:
    intraday: IntradayRealizedMeasures = {
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "sampling_minutes": 5,
        "price_basis": "as_printed",
        "observation_count": 54,
        "realized_variance": 0.02,
        "realized_quarticity": 0.001,
        "positive_semivariance": 0.012,
        "negative_semivariance": 0.008,
        "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
    }

    result = calculate_daily_realized_measures(intraday, 0.01)

    assert result["algorithm_version"] == XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION
    assert result["observation_count"] == 54
