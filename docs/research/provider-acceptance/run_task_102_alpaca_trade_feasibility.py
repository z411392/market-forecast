import json
import math
import os
import re
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import httpx

SYMBOLS = ("AAPL", "NVDA")
SESSION_DATE = date(2026, 9, 24)
PAGE_LIMIT = 10_000
PAGE_SLEEP_SECONDS = 0.4
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-102-alpaca-trade-feasibility"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
_TIMESTAMP_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(\d{1,9}))?Z$"
)


def main() -> None:
    key_id = _required_secret("MARKET_FORECAST_ALPACA_API_KEY_ID")
    secret_key = _required_secret("MARKET_FORECAST_ALPACA_SECRET_KEY")
    calendar = xcals.get_calendar("XNAS")
    label = SESSION_DATE.isoformat()
    session_open = calendar.session_open(label).to_pydatetime()
    session_close = calendar.session_close(label).to_pydatetime()
    if session_open.tzinfo is None or session_close.tzinfo is None:
        raise RuntimeError("task102_calendar_time_not_aware")

    start_text = _format_utc(session_open)
    end_text = _format_utc(session_close - timedelta(microseconds=1))
    start_ns = _datetime_to_ns(session_open)
    end_exclusive_ns = _datetime_to_ns(session_close)

    if OUTPUT_ROOT.exists():
        import shutil

        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "task": 102,
        "provider": "alpaca",
        "feed": "sip",
        "endpoint": "/v2/stocks/{symbol}/trades",
        "session_date": SESSION_DATE.isoformat(),
        "session_start_utc": session_open.isoformat(),
        "session_end_utc_exclusive": session_close.isoformat(),
        "limit": PAGE_LIMIT,
        "page_sleep_seconds": PAGE_SLEEP_SECONDS,
        "status": "running",
        "symbols": [],
    }
    _write_summary(summary)

    with httpx.Client(timeout=60.0) as client:
        for symbol in SYMBOLS:
            result = _capture_symbol(
                client=client,
                symbol=symbol,
                key_id=key_id,
                secret_key=secret_key,
                start_text=start_text,
                end_text=end_text,
                start_ns=start_ns,
                end_exclusive_ns=end_exclusive_ns,
            )
            summary["symbols"].append(result)
            _write_summary(summary)

    total_pages = sum(item["page_count"] for item in summary["symbols"])
    total_trades = sum(item["trade_count"] for item in summary["symbols"])
    total_bytes = sum(item["raw_response_bytes"] for item in summary["symbols"])
    symbol_days = len(SYMBOLS)
    panel_symbol_days = 506

    summary["observed_totals"] = {
        "symbol_days": symbol_days,
        "page_count": total_pages,
        "trade_count": total_trades,
        "raw_response_bytes": total_bytes,
    }
    summary["panel_projection"] = {
        "target_symbol_days": panel_symbol_days,
        "projected_page_requests": (
            total_pages / symbol_days * panel_symbol_days
        ),
        "projected_raw_response_bytes": (
            total_bytes / symbol_days * panel_symbol_days
        ),
        "projected_raw_response_mib": (
            total_bytes / symbol_days * panel_symbol_days / (1024 * 1024)
        ),
        "planning_only": True,
        "full_panel_authorized": False,
    }
    summary["status"] = "accepted"
    _write_summary(summary)


def _capture_symbol(
    *,
    client: httpx.Client,
    symbol: str,
    key_id: str,
    secret_key: str,
    start_text: str,
    end_text: str,
    start_ns: int,
    end_exclusive_ns: int,
) -> dict[str, Any]:
    page_dir = OUTPUT_ROOT / "pages" / symbol
    page_dir.mkdir(parents=True, exist_ok=True)

    page_token: str | None = None
    page_number = 0
    trade_count = 0
    raw_bytes = 0
    previous_ns: int | None = None
    duplicate_timestamp_count = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    condition_counts: Counter[str] = Counter()
    exchange_counts: Counter[str] = Counter()
    page_receipts: list[dict[str, Any]] = []
    rate_limit_snapshots: list[dict[str, str | None]] = []

    while True:
        params: list[tuple[str, str]] = [
            ("start", start_text),
            ("end", end_text),
            ("feed", "sip"),
            ("sort", "asc"),
            ("limit", str(PAGE_LIMIT)),
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
                f"task102_provider_http_status:{symbol}:{response.status_code}"
            )

        page_number += 1
        raw = response.content
        raw_bytes += len(raw)
        page_path = page_dir / f"page-{page_number:04d}.json"
        page_path.write_bytes(raw)

        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("task102_invalid_response_object")
        if payload.get("symbol") != symbol:
            raise RuntimeError(f"task102_symbol_mismatch:{symbol}")
        trades = payload.get("trades")
        if not isinstance(trades, list):
            raise RuntimeError(f"task102_invalid_trades:{symbol}")

        page_first: str | None = None
        page_last: str | None = None
        for trade in trades:
            if not isinstance(trade, dict):
                raise RuntimeError("task102_invalid_trade_object")
            timestamp = trade.get("t")
            timestamp_ns = _timestamp_to_ns(timestamp)
            if not start_ns <= timestamp_ns < end_exclusive_ns:
                raise RuntimeError(
                    f"task102_trade_outside_session:{symbol}:{timestamp}"
                )
            if previous_ns is not None:
                if timestamp_ns < previous_ns:
                    raise RuntimeError(
                        f"task102_decreasing_timestamp:{symbol}"
                    )
                if timestamp_ns == previous_ns:
                    duplicate_timestamp_count += 1
            previous_ns = timestamp_ns

            if first_timestamp is None:
                first_timestamp = str(timestamp)
            last_timestamp = str(timestamp)
            if page_first is None:
                page_first = str(timestamp)
            page_last = str(timestamp)

            price = trade.get("p")
            size = trade.get("s")
            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or not math.isfinite(float(price))
                or float(price) <= 0.0
            ):
                raise RuntimeError("task102_invalid_trade_price")
            if (
                isinstance(size, bool)
                or not isinstance(size, (int, float))
                or not math.isfinite(float(size))
                or float(size) <= 0.0
            ):
                raise RuntimeError("task102_invalid_trade_size")

            exchange = trade.get("x")
            if not isinstance(exchange, str) or not exchange:
                raise RuntimeError("task102_invalid_exchange_code")
            exchange_counts[exchange] += 1

            conditions = trade.get("c", [])
            if conditions is None:
                conditions = []
            if not isinstance(conditions, list) or any(
                not isinstance(value, str) for value in conditions
            ):
                raise RuntimeError("task102_invalid_trade_conditions")
            condition_counts.update(conditions)
            trade_count += 1

        next_token = payload.get("next_page_token")
        if next_token is not None and (
            not isinstance(next_token, str) or not next_token
        ):
            raise RuntimeError("task102_invalid_next_page_token")

        page_receipts.append(
            {
                "page_number": page_number,
                "trade_count": len(trades),
                "raw_response_bytes": len(raw),
                "raw_sha256": sha256(raw).hexdigest(),
                "first_timestamp": page_first,
                "last_timestamp": page_last,
                "has_next_page": next_token is not None,
            }
        )
        rate_limit_snapshots.append(
            {
                "page_number": str(page_number),
                "limit": response.headers.get("x-ratelimit-limit"),
                "remaining": response.headers.get("x-ratelimit-remaining"),
                "reset": response.headers.get("x-ratelimit-reset"),
            }
        )

        if next_token is None:
            break
        if next_token == page_token:
            raise RuntimeError("task102_repeated_page_token")
        page_token = next_token
        time.sleep(PAGE_SLEEP_SECONDS)

    if trade_count == 0:
        raise RuntimeError(f"task102_empty_regular_session:{symbol}")

    return {
        "symbol": symbol,
        "page_count": page_number,
        "trade_count": trade_count,
        "raw_response_bytes": raw_bytes,
        "bytes_per_trade": raw_bytes / trade_count,
        "first_trade_timestamp": first_timestamp,
        "last_trade_timestamp": last_timestamp,
        "timestamps_non_decreasing": True,
        "duplicate_timestamp_adjacency_count": duplicate_timestamp_count,
        "condition_frequency": dict(condition_counts.most_common()),
        "exchange_frequency": dict(exchange_counts.most_common()),
        "page_receipts": page_receipts,
        "rate_limit_snapshots": rate_limit_snapshots,
    }


def _timestamp_to_ns(value: object) -> int:
    if not isinstance(value, str):
        raise RuntimeError("task102_invalid_trade_timestamp")
    match = _TIMESTAMP_RE.fullmatch(value)
    if match is None:
        raise RuntimeError(f"task102_invalid_trade_timestamp:{value}")
    base_text, fraction = match.groups()
    base = datetime.fromisoformat(base_text).replace(tzinfo=timezone.utc)
    fraction_ns = int((fraction or "").ljust(9, "0"))
    return int(base.timestamp()) * 1_000_000_000 + fraction_ns


def _datetime_to_ns(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise RuntimeError("task102_datetime_not_utc")
    return (
        int(value.timestamp()) * 1_000_000_000
        + value.microsecond * 1_000
    )


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


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
