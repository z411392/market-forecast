import gzip
import json
import math
import os
import re
import shutil
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import httpx

PLAN_PATH = Path(
    "docs/research/provider-acceptance/task-105-us-transaction-rk-plan.json"
)
REQUEST_PATH = Path(
    "docs/research/provider-acceptance/task-105-trade-batch-request.json"
)
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-105-us-transaction-rk-batch"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"

ELIGIBLE_CONDITIONS = frozenset(
    ("@", "A", "B", "D", "F", "K", "L", "O", "T", "X", "Y", "5", "6")
)
INELIGIBLE_CONDITIONS = frozenset(
    ("C", "G", "H", "I", "M", "N", "P", "Q", "R", "U", "V", "W", "Z", "4", "7", "9")
)
KNOWN_CONDITIONS = ELIGIBLE_CONDITIONS | INELIGIBLE_CONDITIONS
_TIMESTAMP_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(\d{1,9}))?Z$"
)


def main() -> None:
    plan = _load_json(PLAN_PATH)
    request = _load_json(REQUEST_PATH)
    batch_number = _require_int(request.get("batch_number"), "invalid_batch_number")
    if request.get("authorized") is not True:
        raise RuntimeError("task105_batch_not_authorized")
    if request.get("provider_calls_allowed") is not True:
        raise RuntimeError("task105_provider_calls_not_allowed")

    batch = _select_batch(plan, batch_number)
    symbols = tuple(_require_str(value, "invalid_symbol") for value in plan["symbols"])
    dates = tuple(date.fromisoformat(_require_str(value, "invalid_date")) for value in batch["dates"])
    page_limit = _require_int(plan["acquisition"]["page_limit"], "invalid_page_limit")
    page_sleep = float(plan["acquisition"]["page_sleep_seconds"])

    key_id = _required_secret("MARKET_FORECAST_ALPACA_API_KEY_ID")
    secret_key = _required_secret("MARKET_FORECAST_ALPACA_SECRET_KEY")
    calendar = xcals.get_calendar("XNAS")

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "task": 105,
        "batch_number": batch_number,
        "status": "running",
        "symbols": list(symbols),
        "dates": [value.isoformat() for value in dates],
        "session_results": [],
        "page_limit": page_limit,
        "page_sleep_seconds": page_sleep,
    }
    _write_summary(summary)

    with httpx.Client(timeout=60.0) as client:
        for session_date in dates:
            label = session_date.isoformat()
            session_open = calendar.session_open(label).to_pydatetime()
            session_close = calendar.session_close(label).to_pydatetime()
            for symbol in symbols:
                result = _capture_symbol_day(
                    client=client,
                    symbol=symbol,
                    session_date=session_date,
                    session_open=session_open,
                    session_close=session_close,
                    key_id=key_id,
                    secret_key=secret_key,
                    page_limit=page_limit,
                    page_sleep=page_sleep,
                )
                summary["session_results"].append(result)
                _write_summary(summary)

    summary["totals"] = {
        "symbol_days": len(summary["session_results"]),
        "page_count": sum(item["page_count"] for item in summary["session_results"]),
        "raw_trade_count": sum(item["raw_trade_count"] for item in summary["session_results"]),
        "eligible_trade_count": sum(
            item["eligible_trade_count"] for item in summary["session_results"]
        ),
        "raw_response_bytes": sum(
            item["raw_response_bytes"] for item in summary["session_results"]
        ),
        "eligible_sequence_bytes_gzip": sum(
            item["eligible_sequence_bytes_gzip"] for item in summary["session_results"]
        ),
    }
    summary["status"] = "accepted"
    _write_summary(summary)


def _capture_symbol_day(
    *,
    client: httpx.Client,
    symbol: str,
    session_date: date,
    session_open: datetime,
    session_close: datetime,
    key_id: str,
    secret_key: str,
    page_limit: int,
    page_sleep: float,
) -> dict[str, Any]:
    session_key = session_date.isoformat()
    root = OUTPUT_ROOT / "sessions" / session_key / symbol
    pages_dir = root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    eligible_path = root / "eligible-trades.jsonl.gz"

    start_text = _format_utc(session_open)
    end_text = _format_utc(session_close - timedelta(microseconds=1))
    start_ns = _datetime_to_ns(session_open)
    end_exclusive_ns = _datetime_to_ns(session_close)

    page_token: str | None = None
    page_number = 0
    raw_trade_count = 0
    eligible_trade_count = 0
    raw_response_bytes = 0
    previous_ns: int | None = None
    eligible_previous_ns: int | None = None
    duplicate_timestamp_count = 0
    eligible_duplicate_timestamp_count = 0
    first_trade_timestamp: str | None = None
    last_trade_timestamp: str | None = None
    first_eligible_timestamp: str | None = None
    last_eligible_timestamp: str | None = None
    condition_counts: Counter[str] = Counter()
    excluded_condition_counts: Counter[str] = Counter()
    exchange_counts: Counter[str] = Counter()
    page_receipts: list[dict[str, Any]] = []

    with gzip.open(eligible_path, "wt", encoding="utf-8", newline="\n") as eligible_file:
        while True:
            params: list[tuple[str, str]] = [
                ("start", start_text),
                ("end", end_text),
                ("feed", "sip"),
                ("sort", "asc"),
                ("limit", str(page_limit)),
            ]
            if page_token is not None:
                params.append(("page_token", page_token))

            response = client.get(
                f"https://data.alpaca.markets/v2/stocks/{symbol}/trades",
                params=params,
                headers={
                    "APCA-API-KEY-ID": key_id,
                    "APCA-API-SECRET-KEY": secret_key,
                    "Accept": "application/json",
                },
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"task105_provider_http_status:{session_key}:{symbol}:{response.status_code}"
                )

            page_number += 1
            raw = response.content
            raw_response_bytes += len(raw)
            raw_sha = sha256(raw).hexdigest()
            page_path = pages_dir / f"page-{page_number:04d}.json"
            page_path.write_bytes(raw)

            payload = response.json()
            if not isinstance(payload, dict) or payload.get("symbol") != symbol:
                raise RuntimeError(f"task105_invalid_page_identity:{session_key}:{symbol}")
            trades = payload.get("trades")
            if not isinstance(trades, list):
                raise RuntimeError(f"task105_invalid_trades:{session_key}:{symbol}")

            page_first: str | None = None
            page_last: str | None = None
            for trade in trades:
                if not isinstance(trade, dict):
                    raise RuntimeError("task105_invalid_trade_object")
                timestamp = trade.get("t")
                timestamp_ns = _timestamp_to_ns(timestamp)
                if not start_ns <= timestamp_ns < end_exclusive_ns:
                    raise RuntimeError(
                        f"task105_trade_outside_session:{session_key}:{symbol}:{timestamp}"
                    )
                if previous_ns is not None:
                    if timestamp_ns < previous_ns:
                        raise RuntimeError(
                            f"task105_decreasing_timestamp:{session_key}:{symbol}"
                        )
                    if timestamp_ns == previous_ns:
                        duplicate_timestamp_count += 1
                previous_ns = timestamp_ns

                if first_trade_timestamp is None:
                    first_trade_timestamp = str(timestamp)
                last_trade_timestamp = str(timestamp)
                if page_first is None:
                    page_first = str(timestamp)
                page_last = str(timestamp)

                price = _positive_number(trade.get("p"), "task105_invalid_price")
                size = _positive_number(trade.get("s"), "task105_invalid_size")
                _ = size

                exchange = trade.get("x")
                if not isinstance(exchange, str) or not exchange:
                    raise RuntimeError("task105_invalid_exchange")
                exchange_counts[exchange] += 1

                conditions = trade.get("c")
                if not isinstance(conditions, list) or not conditions:
                    raise RuntimeError(
                        f"task105_missing_conditions:{session_key}:{symbol}"
                    )
                if any(not isinstance(value, str) for value in conditions):
                    raise RuntimeError("task105_invalid_condition_type")
                unknown = set(conditions) - KNOWN_CONDITIONS
                if unknown:
                    raise RuntimeError(
                        f"task105_unknown_condition:{session_key}:{symbol}:{sorted(unknown)}"
                    )
                condition_counts.update(conditions)
                raw_trade_count += 1

                if all(value in ELIGIBLE_CONDITIONS for value in conditions):
                    if eligible_previous_ns is not None:
                        if timestamp_ns < eligible_previous_ns:
                            raise RuntimeError("task105_eligible_decreasing_timestamp")
                        if timestamp_ns == eligible_previous_ns:
                            eligible_duplicate_timestamp_count += 1
                    eligible_previous_ns = timestamp_ns
                    if first_eligible_timestamp is None:
                        first_eligible_timestamp = str(timestamp)
                    last_eligible_timestamp = str(timestamp)
                    eligible_file.write(
                        json.dumps(
                            {"t": timestamp, "p": price},
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    eligible_trade_count += 1
                else:
                    for value in conditions:
                        if value in INELIGIBLE_CONDITIONS:
                            excluded_condition_counts[value] += 1

            next_token = payload.get("next_page_token")
            if next_token is not None and (
                not isinstance(next_token, str) or not next_token
            ):
                raise RuntimeError("task105_invalid_next_page_token")

            page_receipts.append(
                {
                    "page_number": page_number,
                    "trade_count": len(trades),
                    "raw_response_bytes": len(raw),
                    "raw_sha256": raw_sha,
                    "first_timestamp": page_first,
                    "last_timestamp": page_last,
                    "has_next_page": next_token is not None,
                }
            )

            if next_token is None:
                break
            if next_token == page_token:
                raise RuntimeError("task105_repeated_page_token")
            page_token = next_token
            time.sleep(page_sleep)

    if raw_trade_count == 0 or eligible_trade_count == 0:
        raise RuntimeError(f"task105_empty_session:{session_key}:{symbol}")

    eligible_bytes = eligible_path.read_bytes()
    summary = {
        "session_date": session_key,
        "symbol": symbol,
        "page_count": page_number,
        "raw_trade_count": raw_trade_count,
        "eligible_trade_count": eligible_trade_count,
        "eligible_trade_fraction": eligible_trade_count / raw_trade_count,
        "raw_response_bytes": raw_response_bytes,
        "eligible_sequence_bytes_gzip": len(eligible_bytes),
        "eligible_sequence_sha256": sha256(eligible_bytes).hexdigest(),
        "first_trade_timestamp": first_trade_timestamp,
        "last_trade_timestamp": last_trade_timestamp,
        "first_eligible_timestamp": first_eligible_timestamp,
        "last_eligible_timestamp": last_eligible_timestamp,
        "duplicate_timestamp_adjacency_count": duplicate_timestamp_count,
        "eligible_duplicate_timestamp_adjacency_count": (
            eligible_duplicate_timestamp_count
        ),
        "condition_frequency": dict(condition_counts.most_common()),
        "excluded_condition_frequency": dict(
            excluded_condition_counts.most_common()
        ),
        "exchange_frequency": dict(exchange_counts.most_common()),
        "page_receipts": page_receipts,
    }
    (root / "session-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _select_batch(plan: dict[str, Any], batch_number: int) -> dict[str, Any]:
    batches = plan.get("batches")
    if not isinstance(batches, list):
        raise RuntimeError("task105_invalid_batches")
    matches = [
        item
        for item in batches
        if isinstance(item, dict) and item.get("batch") == batch_number
    ]
    if len(matches) != 1:
        raise RuntimeError("task105_batch_identity_mismatch")
    return matches[0]


def _timestamp_to_ns(value: object) -> int:
    if not isinstance(value, str):
        raise RuntimeError("task105_invalid_timestamp")
    match = _TIMESTAMP_RE.fullmatch(value)
    if match is None:
        raise RuntimeError(f"task105_invalid_timestamp:{value}")
    base_text, fraction = match.groups()
    base = datetime.fromisoformat(base_text).replace(tzinfo=timezone.utc)
    fraction_ns = int((fraction or "").ljust(9, "0"))
    return int(base.timestamp()) * 1_000_000_000 + fraction_ns


def _datetime_to_ns(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise RuntimeError("task105_datetime_not_utc")
    return int(value.timestamp()) * 1_000_000_000 + value.microsecond * 1_000


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _positive_number(value: object, error: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise RuntimeError(error)
    return float(value)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"task105_invalid_json_object:{path}")
    return value


def _require_int(value: object, error: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(error)
    return value


def _require_str(value: object, error: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(error)
    return value


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _write_summary(summary: dict[str, Any]) -> None:
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
