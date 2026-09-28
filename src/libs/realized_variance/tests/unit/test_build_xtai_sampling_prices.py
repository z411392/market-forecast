from datetime import date, datetime, timedelta, timezone

from pytest import mark, raises

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.closing_auction_observation import ClosingAuctionObservation
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.session_open_price_observation import SessionOpenPriceObservation
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


def _session_open(
    source_interval_start_utc: datetime | None = None,
    price: float = 100.0,
) -> SessionOpenPriceObservation:
    return {
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "source_interval_start_utc": source_interval_start_utc
        or datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc),
        "price": price,
        "price_basis": "as_printed",
    }


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
    expected_counts = {5: 54, 10: 27, 15: 18}

    for interval, expected_count in expected_counts.items():
        sampled = build_xtai_sampling_prices(
            _bars(),
            _session_open(),
            _closing(),
            interval,
        )

        assert len(sampled) == expected_count
        assert sampled[0]["role"] == "regular_interval_close"
        assert sampled[0]["observed_at_utc"] == datetime(
            2026,
            9,
            24,
            1,
            interval,
            tzinfo=timezone.utc,
        )
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

    bars_5m = build_xtai_sampling_prices(
        _bars(),
        _session_open(),
        _closing(),
        5,
    )
    assert bars_5m[0]["price"] == _bars()[4]["close"]

    delayed_bars = _bars()[2:]
    delayed_open = _session_open(
        source_interval_start_utc=delayed_bars[0]["bar_start_utc"],
        price=delayed_bars[0]["open"],
    )
    delayed_5m = build_xtai_sampling_prices(
        delayed_bars,
        delayed_open,
        _closing(),
        5,
    )
    assert len(delayed_5m) == 54
    assert delayed_5m[0]["observed_at_utc"] == datetime(
        2026,
        9,
        24,
        1,
        5,
        tzinfo=timezone.utc,
    )
    assert delayed_5m[0]["price"] == _bars()[4]["close"]

    sparse = tuple(bar for index, bar in enumerate(_bars()) if index != 54)
    sparse_5m = build_xtai_sampling_prices(
        sparse,
        _session_open(),
        _closing(),
        5,
    )
    assert len(sparse_5m) == 54
    assert sparse_5m[10]["observed_at_utc"] == datetime(
        2026,
        9,
        24,
        1,
        55,
        tzinfo=timezone.utc,
    )
    assert sparse_5m[10]["price"] == _bars()[53]["close"]

    missing_last_regular_minute = _bars()[:-1]
    sparse_close_5m = build_xtai_sampling_prices(
        missing_last_regular_minute,
        _session_open(),
        _closing(),
        5,
    )
    assert sparse_close_5m[-2]["price"] == _bars()[-2]["close"]

    empty_internal_bucket = tuple(
        bar
        for index, bar in enumerate(_bars())
        if index not in range(50, 55)
    )
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(
            empty_internal_bucket,
            _session_open(),
            _closing(),
            5,
        )

    no_trade_in_first_5m = _bars()[5:]
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(
            no_trade_in_first_5m,
            _session_open(
                source_interval_start_utc=no_trade_in_first_5m[0]["bar_start_utc"],
                price=no_trade_in_first_5m[0]["open"],
            ),
            _closing(),
            5,
        )

    mismatched_open = _session_open(price=999.0)
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(
            _bars(),
            mismatched_open,
            _closing(),
            5,
        )

    out_of_order = list(_bars())
    out_of_order[10], out_of_order[11] = out_of_order[11], out_of_order[10]
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(
            tuple(out_of_order),
            _session_open(),
            _closing(),
            5,
        )

    synthetic_auction_minute = {
        **_bars()[-1],
        "bar_start_utc": datetime(2026, 9, 24, 5, 25, tzinfo=timezone.utc),
    }
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(
            (*_bars(), synthetic_auction_minute),
            _session_open(),
            _closing(),
            5,
        )

    wrong_close = {
        **_closing(),
        "matched_at_utc": datetime(2026, 9, 24, 5, 29, tzinfo=timezone.utc),
    }
    with raises(InvalidRealizedVarianceInputError):
        build_xtai_sampling_prices(
            _bars(),
            _session_open(),
            wrong_close,
            5,
        )
