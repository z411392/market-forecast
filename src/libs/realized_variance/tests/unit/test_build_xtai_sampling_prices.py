from datetime import date, datetime, timedelta, timezone

from pytest import mark, raises

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.closing_auction_observation import ClosingAuctionObservation
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.build_xtai_sampling_prices import (
    build_xtai_sampling_prices,
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


def _bars() -> tuple[CanonicalMinuteBar, ...]:
    start = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
    items: list[CanonicalMinuteBar] = []
    for index in range(265):
        opening = 100.0 + 0.01 * index
        items.append(
            {
                "security": _security(),
                "bar_start_utc": start + timedelta(minutes=index),
                "session_date": date(2026, 9, 24),
                "open": opening,
                "high": opening + 0.02,
                "low": opening - 0.02,
                "close": opening + 0.01,
                "volume": 100.0 + index,
                "price_basis": "as_printed",
            }
        )
    return tuple(items)


def _closing() -> ClosingAuctionObservation:
    return {
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "matched_at_utc": datetime(2026, 9, 24, 5, 30, tzinfo=timezone.utc),
        "price": 103.0,
        "volume": 5000.0,
        "price_basis": "as_printed",
    }


@mark.unit
def test_build_xtai_sampling_prices() -> None:
    expected_counts = {5: 55, 10: 28, 15: 19}

    for interval, expected_count in expected_counts.items():
        sampled = build_xtai_sampling_prices(_bars(), _closing(), interval)

        assert len(sampled) == expected_count
        assert sampled[0]["role"] == "session_open"
        assert sampled[0]["observed_at_utc"] == datetime(
            2026,
            9,
            24,
            1,
            0,
            tzinfo=timezone.utc,
        )
        assert sampled[0]["price"] == 100.0
        assert sampled[-1]["role"] == "closing_auction_close"
        assert sampled[-1]["observed_at_utc"] == datetime(
            2026,
            9,
            24,
            5,
            30,
            tzinfo=timezone.utc,
        )
        assert sampled[-1]["price"] == 103.0
        assert sampled[-1]["algorithm_version"] == XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION

        for previous, current in zip(sampled, sampled[1:]):
            assert current["observed_at_utc"] - previous["observed_at_utc"] == timedelta(
                minutes=interval
            )

    bars_5m = build_xtai_sampling_prices(_bars(), _closing(), 5)
    assert bars_5m[1]["price"] == _bars()[4]["close"]

    missing_regular_minute = _bars()[:-1]
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(missing_regular_minute, _closing(), 5)

    synthetic_auction_minute = {
        **_bars()[-1],
        "bar_start_utc": datetime(2026, 9, 24, 5, 25, tzinfo=timezone.utc),
    }
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices((*_bars(), synthetic_auction_minute), _closing(), 5)

    wrong_close = {
        **_closing(),
        "matched_at_utc": datetime(2026, 9, 24, 5, 29, tzinfo=timezone.utc),
    }
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(_bars(), wrong_close, 5)
