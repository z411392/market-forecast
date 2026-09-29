import json
import math
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import shioaji as sj

SYMBOL = "2454"
SESSION_DATE = date(2026, 5, 4)
BUCKET_START = time(11, 25)
BUCKET_END = time(11, 30)
OUTPUT = Path(
    "artifacts/private/provider-captures/task-89-empty-bucket-diagnostic/summary.json"
)


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret("MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )
        contract = api.contracts.get(SYMBOL)
        if contract is None:
            raise RuntimeError("shioaji_contract_2454_not_found")

        ticks = _normalize_payload(
            api.ticks(
                contract=contract,
                date=SESSION_DATE.isoformat(),
                query_type=sj.constant.TicksQueryType.AllDay,
            ).dict()
        )
        kbars = _normalize_payload(
            api.kbars(
                contract=contract,
                start=SESSION_DATE.isoformat(),
                end=SESSION_DATE.isoformat(),
                timeout=15000,
            ).dict()
        )
    finally:
        try:
            api.logout()
        except Exception:
            pass

    summary = _diagnose(ticks, kbars)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _diagnose(
    ticks: dict[str, list[int | float]],
    kbars: dict[str, list[int | float]],
) -> dict[str, Any]:
    tick_times = [_wall_clock(value) for value in ticks["ts"]]
    tick_prices = [float(value) for value in ticks["close"]]
    if len(tick_times) != len(tick_prices):
        raise RuntimeError("inconsistent_tick_lengths")

    bucket_start = datetime.combine(SESSION_DATE, BUCKET_START)
    bucket_end = datetime.combine(SESSION_DATE, BUCKET_END)

    in_bucket = [
        index
        for index, tick_time in enumerate(tick_times)
        if bucket_start <= tick_time < bucket_end
    ]
    at_boundary = [
        index
        for index, tick_time in enumerate(tick_times)
        if tick_time == bucket_end
    ]
    before_start = [
        index
        for index, tick_time in enumerate(tick_times)
        if tick_time <= bucket_start
    ]
    at_or_before_end = [
        index
        for index, tick_time in enumerate(tick_times)
        if tick_time <= bucket_end
    ]
    after_end = [
        index
        for index, tick_time in enumerate(tick_times)
        if tick_time > bucket_end
    ]

    last_at_or_before_start = _tick_record(
        ticks,
        tick_times,
        tick_prices,
        before_start[-1] if before_start else None,
    )
    previous_tick_at_boundary = _tick_record(
        ticks,
        tick_times,
        tick_prices,
        at_or_before_end[-1] if at_or_before_end else None,
    )
    first_after_boundary = _tick_record(
        ticks,
        tick_times,
        tick_prices,
        after_end[0] if after_end else None,
    )

    if previous_tick_at_boundary is None:
        raise RuntimeError("missing_previous_tick_at_boundary")

    previous_tick_time = datetime.fromisoformat(previous_tick_at_boundary["local"])
    staleness_seconds = (bucket_end - previous_tick_time).total_seconds()

    kbar_records = _kbar_records(kbars)
    surrounding = [
        record
        for record in kbar_records
        if time(11, 15) <= record["label_time"] <= time(11, 40)
    ]
    label_set = {record["label"] for record in kbar_records}
    expected_empty_labels = [
        datetime.combine(SESSION_DATE, time(11, minute)).strftime("%H:%M")
        for minute in range(26, 31)
    ]

    preceding_label = datetime.combine(SESSION_DATE, time(11, 25))
    preceding_kbar = next(
        (record for record in kbar_records if record["label_dt"] == preceding_label),
        None,
    )
    next_label_after_gap = min(
        (
            record
            for record in kbar_records
            if record["label_dt"] > bucket_end
        ),
        key=lambda record: record["label_dt"],
        default=None,
    )

    return {
        "task": 89,
        "diagnostic_version": "empty-fixed-grid-bucket-v1",
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "symbol": SYMBOL,
        "session_date": SESSION_DATE.isoformat(),
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "bucket": {
            "start_local": bucket_start.isoformat(),
            "end_local": bucket_end.isoformat(),
            "tick_count_inside_half_open_bucket": len(in_bucket),
            "tick_count_exactly_at_boundary": len(at_boundary),
            "expected_missing_kbar_end_labels": expected_empty_labels,
            "all_expected_kbar_labels_absent": all(
                label not in label_set for label in expected_empty_labels
            ),
        },
        "previous_tick_rule": {
            "last_tick_at_or_before_bucket_start": last_at_or_before_start,
            "price_at_11_30_boundary": previous_tick_at_boundary["price"],
            "source_tick": previous_tick_at_boundary,
            "staleness_seconds_at_boundary": staleness_seconds,
            "first_tick_after_boundary": first_after_boundary,
            "uses_actual_prior_transaction": True,
            "creates_transaction_at_boundary": False,
            "creates_minute_bar": False,
        },
        "surrounding_kbars": [
            _serializable_kbar(record) for record in surrounding
        ],
        "preceding_kbar_11_25": (
            _serializable_kbar(preceding_kbar)
            if preceding_kbar is not None
            else None
        ),
        "first_kbar_after_11_30": (
            _serializable_kbar(next_label_after_gap)
            if next_label_after_gap is not None
            else None
        ),
        "status": "complete",
    }


def _tick_record(
    payload: dict[str, list[int | float]],
    tick_times: list[datetime],
    tick_prices: list[float],
    index: int | None,
) -> dict[str, Any] | None:
    if index is None:
        return None
    return {
        "local": tick_times[index].isoformat(),
        "price": tick_prices[index],
        "volume": _optional_number_at(payload, "volume", index),
        "tick_type": _optional_number_at(payload, "tick_type", index),
    }


def _kbar_records(
    payload: dict[str, list[int | float]],
) -> list[dict[str, Any]]:
    count = len(payload["ts"])
    for field in ("Open", "High", "Low", "Close", "Volume"):
        if len(payload[field]) != count:
            raise RuntimeError("inconsistent_kbar_lengths")

    records: list[dict[str, Any]] = []
    for index in range(count):
        label_dt = _wall_clock(payload["ts"][index])
        if label_dt.date() != SESSION_DATE:
            raise RuntimeError("kbar_session_date_mismatch")
        records.append(
            {
                "label_dt": label_dt,
                "label": label_dt.strftime("%H:%M"),
                "label_time": label_dt.time(),
                "open": float(payload["Open"][index]),
                "high": float(payload["High"][index]),
                "low": float(payload["Low"][index]),
                "close": float(payload["Close"][index]),
                "volume": float(payload["Volume"][index]),
            }
        )
    return records


def _serializable_kbar(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "label_local": record["label_dt"].isoformat(),
        "open": record["open"],
        "high": record["high"],
        "low": record["low"],
        "close": record["close"],
        "volume": record["volume"],
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


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


if __name__ == "__main__":
    main()
