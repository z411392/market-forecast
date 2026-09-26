from datetime import date, datetime, timedelta, timezone

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.domain.services.aggregate_minute_bars import aggregate_minute_bars
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)
from pytest import approx, mark, raises


def _security() -> SecurityIdentity:
    return {
        "symbol": "TEST",
        "exchange": "XNYS",
        "timezone": "America/New_York",
        "calendar_id": "XNYS",
    }


def _minute_bar(index: int, start: datetime) -> CanonicalMinuteBar:
    opening = 100.0 + 0.1 * index
    return {
        "security": _security(),
        "bar_start_utc": start + timedelta(minutes=index),
        "session_date": date(2026, 9, 25),
        "open": opening,
        "high": opening + 0.2,
        "low": opening - 0.2,
        "close": opening + 0.1,
        "volume": 100.0 + index,
        "price_basis": "as_printed",
    }


@mark.unit
def test_aggregate_minute_bars() -> None:
    start = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)
    bars = tuple(_minute_bar(index, start) for index in range(30))

    bars_5m = aggregate_minute_bars(bars, 5, start)
    bars_10m = aggregate_minute_bars(bars, 10, start)
    bars_15m = aggregate_minute_bars(bars, 15, start)

    assert len(bars_5m) == 6
    assert len(bars_10m) == 3
    assert len(bars_15m) == 2

    first_5m = bars_5m[0]
    assert first_5m["bar_start_utc"] == start
    assert first_5m["interval_minutes"] == 5
    assert first_5m["source_minute_count"] == 5
    assert first_5m["open"] == approx(100.0)
    assert first_5m["high"] == approx(100.6)
    assert first_5m["low"] == approx(99.8)
    assert first_5m["close"] == approx(100.5)
    assert first_5m["volume"] == approx(510.0)
    assert first_5m["price_basis"] == "as_printed"

    assert bars_10m[0]["close"] == approx(101.0)
    assert bars_10m[0]["volume"] == approx(1045.0)
    assert bars_15m[0]["close"] == approx(101.5)
    assert bars_15m[0]["volume"] == approx(1605.0)

    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(bars, 7, start)

    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars((), 5, start)

    naive = list(bars)
    naive[0] = {**naive[0], "bar_start_utc": naive[0]["bar_start_utc"].replace(tzinfo=None)}
    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(tuple(naive), 5, start)

    shifted = start + timedelta(minutes=1)
    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(bars, 5, shifted)

    gapped = list(bars)
    gapped[5] = {**gapped[5], "bar_start_utc": start + timedelta(minutes=6)}
    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(tuple(gapped), 5, start)

    out_of_order = list(bars)
    out_of_order[5], out_of_order[6] = out_of_order[6], out_of_order[5]
    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(tuple(out_of_order), 5, start)

    other_security = {
        "symbol": "OTHER",
        "exchange": "XNYS",
        "timezone": "America/New_York",
        "calendar_id": "XNYS",
    }
    mixed_security = list(bars)
    mixed_security[10] = {**mixed_security[10], "security": other_security}
    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(tuple(mixed_security), 5, start)

    mixed_session = list(bars)
    mixed_session[10] = {**mixed_session[10], "session_date": date(2026, 9, 26)}
    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(tuple(mixed_session), 5, start)

    mixed_basis = list(bars)
    mixed_basis[10] = {**mixed_basis[10], "price_basis": "split_adjusted"}
    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(tuple(mixed_basis), 5, start)

    with raises(InvalidRealizedVarianceInputError):
        aggregate_minute_bars(bars[:-1], 5, start)
