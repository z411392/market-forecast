import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import shioaji as sj


SYMBOL = "2330"
SESSIONS = (date(2026, 9, 24), date(2026, 8, 24))
OUTPUT = Path(
    "artifacts/private/provider-captures/task-89-tick-kbar-diagnostic/summary.json"
)


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret("MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    summary: dict[str, Any] = {
        "task": 89,
        "diagnostic": "shioaji_tick_vs_historical_kbar",
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
            raise RuntimeError("shioaji_contract_2330_not_found")

        for session_date in SESSIONS:
            ticks = api.ticks(contract=contract, date=session_date.isoformat())
            kbars = api.kbars(
                contract=contract,
                start=session_date.isoformat(),
                end=session_date.isoformat(),
                timeout=15000,
            )
            summary["sessions"].append(
                _diagnose_session(
                    session_date,
                    _normalize_payload(ticks.dict()),
                    _normalize_payload(kbars.dict()),
                )
            )
            _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass

    summary["status"] = "complete"
    _write_summary(summary)


def _diagnose_session(
    session_date: date,
    ticks: dict[str, list[int | float]],
    kbars: dict[str, list[int | float]],
) -> dict[str, Any]:
    tick_prices_by_minute: dict[datetime, list[float]] = defaultdict(list)
    for raw_ts, close in zip(ticks["ts"], ticks["close"], strict=True):
        if not isinstance(raw_ts, int):
            raise RuntimeError("unexpected_tick_timestamp_type")
        if not isinstance(close, (int, float)) or isinstance(close, bool):
            raise RuntimeError("unexpected_tick_price_type")
        seconds, _ = divmod(raw_ts, 1_000_000_000)
        wall_clock = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
            tzinfo=None
        )
        if wall_clock.date() != session_date:
            raise RuntimeError("tick_session_date_mismatch")
        minute = wall_clock.replace(second=0, microsecond=0)
        tick_prices_by_minute[minute].append(float(close))

    kbar_records = _kbar_records(kbars, session_date)
    regular_records = [
        record
        for record in kbar_records
        if record["label"].strftime("%H:%M") != "13:30"
    ]

    end_label_match_count = 0
    start_label_match_count = 0
    comparable_end_label_count = 0
    comparable_start_label_count = 0

    for record in regular_records:
        label = record["label"]
        end_window = tick_prices_by_minute.get(label - timedelta(minutes=1))
        start_window = tick_prices_by_minute.get(label)

        if end_window:
            comparable_end_label_count += 1
            if _ohlc_matches(record, end_window):
                end_label_match_count += 1
        if start_window:
            comparable_start_label_count += 1
            if _ohlc_matches(record, start_window):
                start_label_match_count += 1

    expected_labels = tuple(
        datetime.combine(session_date, datetime.min.time()).replace(
            hour=9,
            minute=1,
        )
        + timedelta(minutes=index)
        for index in range(265)
    ) + (
        datetime.combine(session_date, datetime.min.time()).replace(
            hour=13,
            minute=30,
        ),
    )
    observed_labels = {record["label"] for record in kbar_records}
    missing_labels = sorted(set(expected_labels) - observed_labels)

    missing_diagnostics = []
    for label in missing_labels:
        previous_minute = label - timedelta(minutes=1)
        missing_diagnostics.append(
            {
                "missing_kbar_label_local": label.strftime("%H:%M"),
                "preceding_minute_tick_count": len(
                    tick_prices_by_minute.get(previous_minute, [])
                ),
                "same_minute_tick_count": len(
                    tick_prices_by_minute.get(label, [])
                ),
                "preceding_minute_ohlc": _ohlc_or_none(
                    tick_prices_by_minute.get(previous_minute)
                ),
                "same_minute_ohlc": _ohlc_or_none(
                    tick_prices_by_minute.get(label)
                ),
            }
        )

    closing_label = datetime.combine(
        session_date,
        datetime.min.time(),
    ).replace(hour=13, minute=30)
    closing_ticks = tick_prices_by_minute.get(closing_label, [])
    closing_kbar = next(
        (
            record
            for record in kbar_records
            if record["label"] == closing_label
        ),
        None,
    )

    return {
        "session_date": session_date.isoformat(),
        "tick_count": len(ticks["ts"]),
        "tick_minute_count": len(tick_prices_by_minute),
        "kbar_count": len(kbar_records),
        "regular_kbar_count": len(regular_records),
        "missing_expected_kbar_count": len(missing_labels),
        "missing_kbar_diagnostics": missing_diagnostics,
        "timestamp_semantics": {
            "end_label_comparable_count": comparable_end_label_count,
            "end_label_ohlc_match_count": end_label_match_count,
            "start_label_comparable_count": comparable_start_label_count,
            "start_label_ohlc_match_count": start_label_match_count,
        },
        "closing_auction": {
            "tick_count_at_13_30_minute": len(closing_ticks),
            "tick_ohlc_at_13_30": _ohlc_or_none(closing_ticks),
            "kbar_13_30_ohlc": (
                {
                    "open": closing_kbar["open"],
                    "high": closing_kbar["high"],
                    "low": closing_kbar["low"],
                    "close": closing_kbar["close"],
                }
                if closing_kbar is not None
                else None
            ),
        },
    }


def _kbar_records(
    payload: dict[str, list[int | float]],
    session_date: date,
) -> list[dict[str, Any]]:
    count = len(payload["ts"])
    required = ("Open", "High", "Low", "Close")
    if any(len(payload[field]) != count for field in required):
        raise RuntimeError("inconsistent_kbar_lengths")

    records = []
    for index, raw_ts in enumerate(payload["ts"]):
        if not isinstance(raw_ts, int):
            raise RuntimeError("unexpected_kbar_timestamp_type")
        seconds, _ = divmod(raw_ts, 1_000_000_000)
        label = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
            tzinfo=None
        )
        if label.date() != session_date:
            raise RuntimeError("kbar_session_date_mismatch")
        records.append(
            {
                "label": label,
                "open": float(payload["Open"][index]),
                "high": float(payload["High"][index]),
                "low": float(payload["Low"][index]),
                "close": float(payload["Close"][index]),
            }
        )
    return records


def _ohlc_matches(record: dict[str, Any], prices: list[float]) -> bool:
    actual = _ohlc(prices)
    expected = (
        record["open"],
        record["high"],
        record["low"],
        record["close"],
    )
    return all(
        math.isclose(left, right, rel_tol=0.0, abs_tol=1e-9)
        for left, right in zip(actual, expected, strict=True)
    )


def _ohlc(prices: list[float]) -> tuple[float, float, float, float]:
    return prices[0], max(prices), min(prices), prices[-1]


def _ohlc_or_none(
    prices: list[float] | None,
) -> dict[str, float] | None:
    if not prices:
        return None
    opening, high, low, closing = _ohlc(prices)
    return {
        "open": opening,
        "high": high,
        "low": low,
        "close": closing,
    }


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
