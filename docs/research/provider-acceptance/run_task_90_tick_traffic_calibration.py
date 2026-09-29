import json
import math
import os
import statistics
import time as time_module
from datetime import date, datetime, time, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import shioaji as sj

CASES = (
    ("2330", date(2026, 9, 24), "active_normal_reference"),
    ("2317", date(2026, 9, 24), "normal_reference"),
    ("2454", date(2026, 5, 4), "locked_limit_low_activity"),
)
TIME_START = time(9, 0, 0)
TIME_END = time(13, 30, 59)
MIN_REMAINING_BYTES = 250 * 1024 * 1024
MAX_RUN_DELTA_BYTES = 250 * 1024 * 1024
PANEL_QUERY_COUNT = 3 * 253
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-90-tick-traffic-calibration"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
REQUIRED_FIELDS = (
    "ts",
    "close",
    "volume",
    "bid_price",
    "bid_volume",
    "ask_price",
    "ask_volume",
    "tick_type",
)


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret("MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "task": 90,
        "calibration_version": "shioaji-tick-traffic-calibration-v1",
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "request": {
            "method": "ticks",
            "query_type": "RangeTime",
            "time_start_local": TIME_START.isoformat(),
            "time_end_local": TIME_END.isoformat(),
            "one_symbol_one_session_per_request": True,
        },
        "traffic_guard": {
            "min_remaining_bytes_before_query": MIN_REMAINING_BYTES,
            "max_current_run_delta_bytes": MAX_RUN_DELTA_BYTES,
        },
        "panel_projection_query_count": PANEL_QUERY_COUNT,
        "cases": [],
    }
    _write_summary(summary)

    api = sj.Shioaji(simulation=False)
    run_start_bytes: int | None = None
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )
        initial = _usage_dict(api.usage())
        run_start_bytes = initial["bytes"]
        summary["initial_usage"] = initial
        if initial["remaining_bytes"] < MIN_REMAINING_BYTES:
            raise RuntimeError("traffic_preflight_remaining_below_guard")
        _write_summary(summary)

        contracts: dict[str, Any] = {}
        for symbol, session_date, role in CASES:
            before = _usage_dict(api.usage())
            if before["remaining_bytes"] < MIN_REMAINING_BYTES:
                raise RuntimeError(
                    f"traffic_remaining_below_guard:{symbol}:{session_date}"
                )
            if before["bytes"] - run_start_bytes >= MAX_RUN_DELTA_BYTES:
                raise RuntimeError("traffic_current_run_delta_guard_reached")

            contract = contracts.get(symbol)
            if contract is None:
                contract = api.contracts.get(symbol)
                if contract is None:
                    raise RuntimeError(f"shioaji_contract_not_found:{symbol}")
                contracts[symbol] = contract

            ticks = api.ticks(
                contract=contract,
                date=session_date.isoformat(),
                query_type=sj.constant.TicksQueryType.RangeTime,
                time_start=TIME_START,
                time_end=TIME_END,
                timeout=15000,
            )
            after = _usage_dict(api.usage())

            payload = _normalize_payload(ticks.dict())
            evidence = _validate_and_persist(
                payload=payload,
                symbol=symbol,
                session_date=session_date,
                role=role,
            )
            delta = after["bytes"] - before["bytes"]
            if delta < 0:
                raise RuntimeError("provider_usage_bytes_decreased")
            evidence["usage_before"] = before
            evidence["usage_after"] = after
            evidence["traffic_delta_bytes"] = delta
            evidence["bytes_per_tick"] = (
                delta / evidence["tick_count"]
                if evidence["tick_count"] > 0
                else None
            )
            summary["cases"].append(evidence)
            _write_summary(summary)

            if after["remaining_bytes"] < MIN_REMAINING_BYTES:
                raise RuntimeError(
                    f"traffic_remaining_below_guard_after_query:{symbol}:{session_date}"
                )
            if after["bytes"] - run_start_bytes >= MAX_RUN_DELTA_BYTES:
                raise RuntimeError("traffic_current_run_delta_guard_reached_after_query")

            time_module.sleep(0.5)

        final_usage = _usage_dict(api.usage())
        summary["final_usage"] = final_usage
        summary["current_run_traffic_delta_bytes"] = (
            final_usage["bytes"] - run_start_bytes
        )

        deltas = [
            int(case["traffic_delta_bytes"])
            for case in summary["cases"]
        ]
        summary["traffic_calibration"] = {
            "query_count": len(deltas),
            "min_tick_day_delta_bytes": min(deltas),
            "median_tick_day_delta_bytes": statistics.median(deltas),
            "max_tick_day_delta_bytes": max(deltas),
            "naive_panel_projection_median_bytes": (
                statistics.median(deltas) * PANEL_QUERY_COUNT
            ),
            "naive_panel_projection_max_bytes": max(deltas) * PANEL_QUERY_COUNT,
            "projection_note": (
                "planning diagnostic only; full collector must shard/cache and "
                "re-check api.usage() before every query"
            ),
        }
        summary["status"] = "accepted"
        _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass


def _validate_and_persist(
    *,
    payload: dict[str, list[int | float]],
    symbol: str,
    session_date: date,
    role: str,
) -> dict[str, Any]:
    for field in REQUIRED_FIELDS:
        if field not in payload:
            raise RuntimeError(f"missing_tick_field:{field}")

    tick_count = len(payload["ts"])
    if tick_count == 0:
        raise RuntimeError(f"empty_tick_response:{symbol}:{session_date}")
    if any(len(payload[field]) != tick_count for field in REQUIRED_FIELDS):
        raise RuntimeError(f"inconsistent_tick_field_lengths:{symbol}:{session_date}")

    timestamps = payload["ts"]
    prices = payload["close"]
    volumes = payload["volume"]
    previous_ts: int | None = None
    duplicate_timestamp_adjacencies = 0
    wall_times: list[datetime] = []

    for index in range(tick_count):
        raw_ts = timestamps[index]
        if not isinstance(raw_ts, int):
            raise RuntimeError("unexpected_tick_timestamp_type")
        if previous_ts is not None:
            if raw_ts < previous_ts:
                raise RuntimeError("tick_timestamps_not_non_decreasing")
            if raw_ts == previous_ts:
                duplicate_timestamp_adjacencies += 1
        previous_ts = raw_ts

        wall = _wall_clock(raw_ts)
        wall_times.append(wall)
        if wall.date() != session_date:
            raise RuntimeError("tick_session_date_mismatch")
        if not TIME_START <= wall.time() <= TIME_END:
            raise RuntimeError("tick_outside_requested_window")

        price = prices[index]
        volume = volumes[index]
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(float(price))
            or float(price) <= 0.0
        ):
            raise RuntimeError("invalid_tick_price")
        if (
            isinstance(volume, bool)
            or not isinstance(volume, (int, float))
            or not math.isfinite(float(volume))
            or float(volume) <= 0.0
        ):
            raise RuntimeError("invalid_tick_volume")

    closing_indices = [
        index
        for index, wall in enumerate(wall_times)
        if wall.hour == 13 and wall.minute == 30
    ]
    if not closing_indices:
        raise RuntimeError(f"missing_1330_closing_trade:{symbol}:{session_date}")
    closing_index = closing_indices[-1]

    normalized_payload = {
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "request": {
            "symbol": symbol,
            "session_date": session_date.isoformat(),
            "query_type": "RangeTime",
            "time_start_local": TIME_START.isoformat(),
            "time_end_local": TIME_END.isoformat(),
        },
        "payload": payload,
    }
    sdk_bytes = _json_bytes(normalized_payload)

    transactions = {
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "transactions": [
            {
                "ts": timestamps[index],
                "price": prices[index],
                "volume": volumes[index],
            }
            for index in range(tick_count)
        ],
    }
    transaction_bytes = _json_bytes(transactions)

    stem = f"{symbol}-{session_date.isoformat()}"
    sdk_path = OUTPUT_ROOT / f"{stem}.sdk.json"
    tx_path = OUTPUT_ROOT / f"{stem}.transactions.json"
    sdk_path.write_bytes(sdk_bytes)
    tx_path.write_bytes(transaction_bytes)

    first_index = 0
    last_index = tick_count - 1
    return {
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "role": role,
        "tick_count": tick_count,
        "sdk_payload_sha256": sha256(sdk_bytes).hexdigest(),
        "transaction_sequence_sha256": sha256(transaction_bytes).hexdigest(),
        "sdk_artifact_path": str(sdk_path),
        "transaction_artifact_path": str(tx_path),
        "duplicate_timestamp_adjacency_count": (
            duplicate_timestamp_adjacencies
        ),
        "first_trade": {
            "local": wall_times[first_index].isoformat(),
            "price": float(prices[first_index]),
            "volume": float(volumes[first_index]),
        },
        "last_trade": {
            "local": wall_times[last_index].isoformat(),
            "price": float(prices[last_index]),
            "volume": float(volumes[last_index]),
        },
        "closing_1330_trade_count": len(closing_indices),
        "closing_trade": {
            "local": wall_times[closing_index].isoformat(),
            "price": float(prices[closing_index]),
            "volume": float(volumes[closing_index]),
        },
    }


def _normalize_payload(payload: dict[str, Any]) -> dict[str, list[int | float]]:
    normalized: dict[str, list[int | float]] = {}
    for field in REQUIRED_FIELDS:
        if field not in payload:
            raise RuntimeError(f"missing_tick_field:{field}")
        values = payload[field]
        if hasattr(values, "tolist"):
            values = values.tolist()
        if not isinstance(values, list):
            values = list(values)
        normalized[field] = [_number(value) for value in values]
    return normalized


def _usage_dict(usage: Any) -> dict[str, int]:
    return {
        "connections": int(usage.connections),
        "bytes": int(usage.bytes),
        "limit_bytes": int(usage.limit_bytes),
        "remaining_bytes": int(usage.remaining_bytes),
    }


def _wall_clock(raw_ts: int) -> datetime:
    seconds, nanoseconds = divmod(raw_ts, 1_000_000_000)
    microseconds = nanoseconds // 1_000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
        tzinfo=None,
        microsecond=microseconds,
    )


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _number(value: Any) -> int | float:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bool):
        raise RuntimeError("boolean_market_data_value")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and math.isfinite(value):
        return float(value)
    raise RuntimeError(f"invalid_market_data_number:{type(value).__name__}")


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _write_summary(summary: dict[str, Any]) -> None:
    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
