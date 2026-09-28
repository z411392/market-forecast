import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import shioaji as sj


SYMBOL = "2317"
SESSIONS = (
    date(2025, 11, 17),
    date(2026, 9, 24),
)
OUTPUT = Path(
    "artifacts/private/provider-captures/task-89-session-open-diagnostic/summary.json"
)


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret("MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    summary: dict[str, Any] = {
        "task": 89,
        "diagnostic_version": "xtai-session-open-v1",
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "symbol": SYMBOL,
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "sessions": [],
    }

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )
        contract = api.contracts.get(SYMBOL)
        if contract is None:
            raise RuntimeError("shioaji_contract_2317_not_found")

        for session_date in SESSIONS:
            ticks = _normalize_payload(
                api.ticks(
                    contract=contract,
                    date=session_date.isoformat(),
                    query_type=sj.constant.TicksQueryType.AllDay,
                ).dict()
            )
            kbars = _normalize_payload(
                api.kbars(
                    contract=contract,
                    start=session_date.isoformat(),
                    end=session_date.isoformat(),
                    timeout=15000,
                ).dict()
            )
            summary["sessions"].append(
                _diagnose(session_date, ticks, kbars)
            )
            _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass

    summary["status"] = "complete"
    _write_summary(summary)


def _diagnose(
    session_date: date,
    ticks: dict[str, list[int | float]],
    kbars: dict[str, list[int | float]],
) -> dict[str, Any]:
    if not ticks.get("ts") or not ticks.get("close"):
        raise RuntimeError(f"no_ticks:{session_date}")
    if not kbars.get("ts") or not kbars.get("Open"):
        raise RuntimeError(f"no_kbars:{session_date}")

    tick_times = [_wall_clock(value) for value in ticks["ts"]]
    tick_prices = [float(value) for value in ticks["close"]]
    first_tick_at = tick_times[0]
    first_tick_price = tick_prices[0]

    kbar_times = [_wall_clock(value) for value in kbars["ts"]]
    first_kbar_label = kbar_times[0]
    first_kbar_open = float(kbars["Open"][0])

    first_kbar_interval_start = first_kbar_label - timedelta(minutes=1)
    first_interval_tick_indices = [
        index
        for index, tick_time in enumerate(tick_times)
        if first_kbar_interval_start <= tick_time < first_kbar_label
    ]
    if not first_interval_tick_indices:
        raise RuntimeError(
            f"first_kbar_has_no_ticks:{session_date}:{first_kbar_label.isoformat()}"
        )

    first_interval_prices = [
        tick_prices[index] for index in first_interval_tick_indices
    ]
    interval_open = first_interval_prices[0]
    interval_high = max(first_interval_prices)
    interval_low = min(first_interval_prices)
    interval_close = first_interval_prices[-1]

    ticks_before_first_interval = sum(
        tick_time < first_kbar_interval_start
        for tick_time in tick_times
    )
    ticks_before_0902 = sum(
        tick_time < datetime.combine(session_date, datetime.min.time()).replace(
            hour=9,
            minute=2,
        )
        for tick_time in tick_times
    )

    first_kbar_values = {
        "open": float(kbars["Open"][0]),
        "high": float(kbars["High"][0]),
        "low": float(kbars["Low"][0]),
        "close": float(kbars["Close"][0]),
    }
    first_interval_values = {
        "open": interval_open,
        "high": interval_high,
        "low": interval_low,
        "close": interval_close,
    }

    return {
        "session_date": session_date.isoformat(),
        "tick_count": len(tick_times),
        "kbar_count": len(kbar_times),
        "first_tick_local": first_tick_at.isoformat(),
        "first_tick_price": first_tick_price,
        "first_tick_volume": _optional_number_at(ticks, "volume", 0),
        "first_tick_type": _optional_number_at(ticks, "tick_type", 0),
        "first_kbar_label_local": first_kbar_label.isoformat(),
        "first_kbar_interval_start_local": first_kbar_interval_start.isoformat(),
        "first_kbar_open": first_kbar_open,
        "first_tick_equals_first_kbar_open": math.isclose(
            first_tick_price,
            first_kbar_open,
            rel_tol=0.0,
            abs_tol=1e-9,
        ),
        "first_kbar_ohlc_matches_preceding_minute_ticks": _ohlc_equal(
            first_kbar_values,
            first_interval_values,
        ),
        "ticks_before_first_kbar_interval": ticks_before_first_interval,
        "ticks_before_09_02": ticks_before_0902,
        "first_kbar_preceding_minute_tick_count": len(
            first_interval_tick_indices
        ),
        "first_kbar_ohlc": first_kbar_values,
        "preceding_minute_tick_ohlc": first_interval_values,
        "first_five_ticks": [
            {
                "local": tick_times[index].isoformat(),
                "price": tick_prices[index],
                "volume": _optional_number_at(ticks, "volume", index),
                "tick_type": _optional_number_at(ticks, "tick_type", index),
            }
            for index in range(min(5, len(tick_times)))
        ],
    }


def _wall_clock(value: int | float) -> datetime:
    if not isinstance(value, int):
        raise RuntimeError("unexpected_timestamp_type")
    seconds, nanoseconds = divmod(value, 1_000_000_000)
    if nanoseconds < 0:
        raise RuntimeError("negative_timestamp_remainder")
    return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(tzinfo=None)


def _normalize_payload(payload: dict[str, Any]) -> dict[str, list[int | float]]:
    normalized: dict[str, list[int | float]] = {}
    for field, values in payload.items():
        if hasattr(values, "tolist"):
            values = values.tolist()
        if not isinstance(values, list):
            try:
                values = list(values)
            except TypeError:
                continue

        normalized_values: list[int | float] = []
        for value in values:
            if hasattr(value, "item"):
                value = value.item()
            if isinstance(value, bool):
                raise RuntimeError("boolean_market_data_value")
            if isinstance(value, int):
                normalized_values.append(int(value))
            elif isinstance(value, float) and math.isfinite(value):
                normalized_values.append(float(value))
            else:
                raise RuntimeError(
                    f"unsupported_market_data_value:{field}:{type(value).__name__}"
                )
        normalized[field] = normalized_values
    return normalized


def _optional_number_at(
    payload: dict[str, list[int | float]],
    field: str,
    index: int,
) -> int | float | None:
    values = payload.get(field)
    if values is None or index >= len(values):
        return None
    return values[index]


def _ohlc_equal(
    left: dict[str, float],
    right: dict[str, float],
) -> bool:
    return all(
        math.isclose(
            left[key],
            right[key],
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for key in ("open", "high", "low", "close")
    )


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _write_summary(summary: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
