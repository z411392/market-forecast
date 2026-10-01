import json
import os
import time
from collections import Counter
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import httpx
import pandas as pd

SYMBOLS = ("AAPL", "NVDA")
SESSION_DATE = date(2026, 9, 24)
MAX_PAGES_PER_SYMBOL = 200
PAGE_LIMIT = 10000
REQUEST_SLEEP_SECONDS = 0.25
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-102-alpaca-trade-feasibility"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"


def main() -> None:
    api_key_id = _required_secret(
        "MARKET_FORECAST_ALPACA_API_KEY_ID"
    )
    secret_key = _required_secret(
        "MARKET_FORECAST_ALPACA_SECRET_KEY"
    )

    calendar = xcals.get_calendar("XNAS")
    label = SESSION_DATE.isoformat()
    session_open = calendar.session_open(label).to_pydatetime()
    session_close = calendar.session_close(label).to_pydatetime()
    request_end = session_close - timedelta(microseconds=1)

    summary: dict[str, Any] = {
        "task": 102,
        "provider": "alpaca",
        "feed": "sip",
        "endpoint": "/v2/stocks/{symbol}/trades",
        "session_date": label,
        "session_start_utc": session_open.isoformat(),
        "session_end_utc_exclusive": session_close.isoformat(),
        "page_limit": PAGE_LIMIT,
        "max_pages_per_symbol": MAX_PAGES_PER_SYMBOL,
        "request_sleep_seconds": REQUEST_SLEEP_SECONDS,
        "status": "running",
        "symbols": [],
    }
    _write_summary(summary)

    headers = {
        "APCA-API-KEY-ID": api_key_id,
        "APCA-API-SECRET-KEY": secret_key,
        "Accept": "application/json",
    }

    with httpx.Client(timeout=60.0) as client:
        for symbol in SYMBOLS:
            result = _fetch_symbol(
                client=client,
                headers=headers,
                symbol=symbol,
                start=_format_rfc3339(session_open),
                end=_format_rfc3339(request_end),
            )
            summary["symbols"].append(result)
            _write_summary(summary)

    page_counts = [
        int(result["page_count"])
        for result in summary["symbols"]
    ]
    trade_counts = [
        int(result["trade_count"])
        for result in summary["symbols"]
    ]
    raw_bytes = [
        int(result["raw_response_bytes"])
        for result in summary["symbols"]
    ]

    summary["planning"] = {
        "observed_symbol_days": len(SYMBOLS),
        "target_symbol_days": 506,
        "average_pages_per_symbol_day": sum(page_counts) / len(page_counts),
        "max_pages_per_symbol_day": max(page_counts),
        "average_trades_per_symbol_day": sum(trade_counts)
        / len(trade_counts),
        "max_trades_per_symbol_day": max(trade_counts),
        "average_raw_bytes_per_symbol_day": sum(raw_bytes)
        / len(raw_bytes),
        "max_raw_bytes_per_symbol_day": max(raw_bytes),
        "naive_projected_pages_average": (
            sum(page_counts) / len(page_counts) * 506
        ),
        "naive_projected_pages_max_envelope": (
            max(page_counts) * 506
        ),
        "naive_projected_raw_bytes_average": (
            sum(raw_bytes) / len(raw_bytes) * 506
        ),
        "naive_projected_raw_bytes_max_envelope": (
            max(raw_bytes) * 506
        ),
    }
    summary["status"] = "accepted"
    _write_summary(summary)


def _fetch_symbol(
    *,
    client: httpx.Client,
    headers: dict[str, str],
    symbol: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    page_token: str | None = None
    page_count = 0
    trade_count = 0
    raw_response_bytes = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    previous_ns: int | None = None
    duplicate_timestamp_adjacency_count = 0
    condition_counts: Counter[str] = Counter()
    exchange_counts: Counter[str] = Counter()
    page_evidence: list[dict[str, Any]] = []

    while True:
        if page_count >= MAX_PAGES_PER_SYMBOL:
            raise RuntimeError(
                f"task102_page_guard:{symbol}:{page_count}"
            )

        params = {
            "start": start,
            "end": end,
            "feed": "sip",
            "sort": "asc",
            "limit": str(PAGE_LIMIT),
        }
        if page_token is not None:
            params["page_token"] = page_token

        response = client.get(
            f"https://data.alpaca.markets/v2/stocks/{symbol}/trades",
            params=params,
            headers=headers,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"task102_provider_http_status:{symbol}:"
                f"{response.status_code}"
            )

        raw = response.content
        raw_response_bytes += len(raw)
        payload = response.json()
        if payload.get("symbol") != symbol:
            raise RuntimeError(
                f"task102_symbol_mismatch:{symbol}"
            )
        trades = payload.get("trades")
        if not isinstance(trades, list):
            raise RuntimeError(
                f"task102_invalid_trades:{symbol}"
            )

        page_count += 1
        page_evidence.append(
            {
                "page": page_count,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "trade_count": len(trades),
                "next_page_token_present": (
                    payload.get("next_page_token") is not None
                ),
            }
        )

        for trade in trades:
            if not isinstance(trade, dict):
                raise RuntimeError(
                    f"task102_invalid_trade:{symbol}"
                )
            timestamp = trade.get("t")
            price = trade.get("p")
            size = trade.get("s")
            exchange = trade.get("x")
            conditions = trade.get("c")

            if not isinstance(timestamp, str):
                raise RuntimeError(
                    f"task102_invalid_timestamp:{symbol}"
                )
            timestamp_ns = int(pd.Timestamp(timestamp).value)
            if (
                previous_ns is not None
                and timestamp_ns < previous_ns
            ):
                raise RuntimeError(
                    f"task102_decreasing_timestamp:{symbol}"
                )
            if (
                previous_ns is not None
                and timestamp_ns == previous_ns
            ):
                duplicate_timestamp_adjacency_count += 1
            previous_ns = timestamp_ns

            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or float(price) <= 0.0
            ):
                raise RuntimeError(
                    f"task102_invalid_price:{symbol}"
                )
            if (
                isinstance(size, bool)
                or not isinstance(size, (int, float))
                or float(size) <= 0.0
            ):
                raise RuntimeError(
                    f"task102_invalid_size:{symbol}"
                )
            if not isinstance(exchange, str) or not exchange:
                raise RuntimeError(
                    f"task102_invalid_exchange:{symbol}"
                )
            if not isinstance(conditions, list):
                raise RuntimeError(
                    f"task102_invalid_conditions:{symbol}"
                )

            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp
            exchange_counts[exchange] += 1
            for condition in conditions:
                if isinstance(condition, str):
                    condition_counts[condition] += 1
            trade_count += 1

        next_token = payload.get("next_page_token")
        if next_token is None:
            break
        if not isinstance(next_token, str) or not next_token:
            raise RuntimeError(
                f"task102_invalid_page_token:{symbol}"
            )
        page_token = next_token
        time.sleep(REQUEST_SLEEP_SECONDS)

    if trade_count == 0:
        raise RuntimeError(
            f"task102_empty_session:{symbol}"
        )

    return {
        "symbol": symbol,
        "status": "accepted",
        "page_count": page_count,
        "trade_count": trade_count,
        "raw_response_bytes": raw_response_bytes,
        "bytes_per_trade": raw_response_bytes / trade_count,
        "first_trade_timestamp": first_timestamp,
        "last_trade_timestamp": last_timestamp,
        "duplicate_timestamp_adjacency_count": (
            duplicate_timestamp_adjacency_count
        ),
        "condition_counts": dict(
            sorted(condition_counts.items())
        ),
        "exchange_counts": dict(
            sorted(exchange_counts.items())
        ),
        "page_evidence": page_evidence,
    }


def _format_rfc3339(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _write_summary(summary: dict[str, Any]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
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
