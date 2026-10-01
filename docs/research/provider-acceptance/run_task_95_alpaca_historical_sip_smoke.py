import json
import os
from pathlib import Path

import httpx

OUTPUT = Path(
    "artifacts/private/provider-captures/"
    "task-95-alpaca-historical-sip-smoke"
)
RAW = OUTPUT / "raw-response.json"
SUMMARY = OUTPUT / "summary.json"


def main() -> None:
    key_id = _required("MARKET_FORECAST_ALPACA_API_KEY_ID")
    secret = _required("MARKET_FORECAST_ALPACA_SECRET_KEY")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    params = {
        "timeframe": "1Min",
        "start": "2024-07-02T13:30:00Z",
        "end": "2024-07-02T19:59:59Z",
        "adjustment": "raw",
        "feed": "sip",
        "sort": "asc",
        "limit": "10000",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            "https://data.alpaca.markets/v2/stocks/AAPL/bars",
            params=params,
            headers={
                "APCA-API-KEY-ID": key_id,
                "APCA-API-SECRET-KEY": secret,
                "Accept": "application/json",
            },
        )

    RAW.write_bytes(response.content)
    summary = {
        "task": 95,
        "provider": "alpaca",
        "case": "AAPL_2024-07-02_regular_raw_sip",
        "status_code": response.status_code,
        "request": {
            "path": "/v2/stocks/AAPL/bars",
            "query": params,
        },
        "response_bytes": len(response.content),
    }
    if response.status_code == 200:
        payload = response.json()
        bars = payload.get("bars")
        summary["bar_count"] = len(bars) if isinstance(bars, list) else None
        summary["next_page_token"] = payload.get("next_page_token")
        summary["symbol"] = payload.get("symbol")
        summary["status"] = "accepted_for_shape_inspection"
    else:
        summary["status"] = "provider_rejected"
    SUMMARY.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    if response.status_code != 200:
        raise RuntimeError(f"alpaca_http_status:{response.status_code}")


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


if __name__ == "__main__":
    main()
