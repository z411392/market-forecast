import json
import math
import os
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import shioaji as sj

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.decode_shioaji_stock_kbars import (
    decode_shioaji_stock_kbars,
)
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.build_xtai_sampling_prices import (
    build_xtai_sampling_prices,
)
from libs.realized_variance.domain.services.calculate_intraday_realized_measures_from_sampled_prices import (
    calculate_intraday_realized_measures_from_sampled_prices,
)

CASES = (
    ("2317", date(2025, 11, 17), "delayed_open_blocker"),
    ("2317", date(2026, 9, 24), "normal_open_reference"),
    ("2330", date(2024, 7, 2), "frozen_ordinary_reference"),
    ("2330", date(2026, 9, 24), "frozen_parity_reference"),
)
OUTPUT = Path("artifacts/private/provider-captures/task-86-xtai-rv/summary.json")
FIELDS = ("ts", "Open", "High", "Low", "Close", "Volume", "Amount")


def main() -> None:
    api_key = os.environ.get("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = os.environ.get("MARKET_FORECAST_SHIOAJI_SECRET_KEY")
    if api_key is None or not api_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_API_KEY")
    if secret_key is None or not secret_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    summary: dict[str, Any] = {
        "task": 86,
        "replay_version": "xtai-session-open-v3-live-replay-v1",
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
        "cases": [],
    }

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key.strip(),
            secret_key=secret_key.strip(),
            subscribe_trade=False,
        )

        contracts: dict[str, Any] = {}
        for symbol, session_date, case_name in CASES:
            contract = contracts.get(symbol)
            if contract is None:
                contract = api.contracts.get(symbol)
                if contract is None:
                    raise RuntimeError(f"shioaji_contract_not_found:{symbol}")
                contracts[symbol] = contract

            provider = api.kbars(
                contract=contract,
                start=session_date.isoformat(),
                end=session_date.isoformat(),
                timeout=15000,
            )
            payload = _normalize_payload(provider.dict())
            payload_bytes = (
                json.dumps(
                    {
                        "provider": "shioaji",
                        "provider_version": sj.__version__,
                        "symbol": symbol,
                        "session_date": session_date.isoformat(),
                        "payload": payload,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")

            security: SecurityIdentity = {
                "symbol": symbol,
                "exchange": "XTAI",
                "timezone": "Asia/Taipei",
                "calendar_id": "XTAI",
            }
            bars, session_open, closing = decode_shioaji_stock_kbars(
                payload,
                security,
                session_date,
                "as_printed",
            )

            interval_results: list[dict[str, object]] = []
            for interval in (5, 10, 15):
                sampled = build_xtai_sampling_prices(
                    bars,
                    session_open,
                    closing,
                    interval,
                )
                measures = calculate_intraday_realized_measures_from_sampled_prices(
                    sampled,
                    session_open,
                )
                expected_observation_count = 270 // interval
                if measures["observation_count"] != expected_observation_count:
                    raise RuntimeError(
                        f"unexpected_observation_count:"
                        f"{symbol}:{session_date}:{interval}"
                    )
                if len(sampled) != expected_observation_count:
                    raise RuntimeError(
                        f"unexpected_sampled_price_count:"
                        f"{symbol}:{session_date}:{interval}"
                    )
                if (
                    measures["algorithm_version"]
                    != XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION
                ):
                    raise RuntimeError(
                        f"unexpected_algorithm_version:"
                        f"{symbol}:{session_date}:{interval}"
                    )

                interval_results.append(
                    {
                        "sampling_minutes": interval,
                        "sampled_price_count": len(sampled),
                        "first_sample_at_utc": sampled[0]["observed_at_utc"].isoformat(),
                        "last_sample_at_utc": sampled[-1]["observed_at_utc"].isoformat(),
                        "observation_count": measures["observation_count"],
                        "regular_session_variance": measures["realized_variance"],
                        "realized_quarticity": measures["realized_quarticity"],
                        "positive_semivariance": measures["positive_semivariance"],
                        "negative_semivariance": measures["negative_semivariance"],
                        "algorithm_version": measures["algorithm_version"],
                    }
                )

            summary["cases"].append(
                {
                    "case": case_name,
                    "symbol": symbol,
                    "session_date": session_date.isoformat(),
                    "provider_bar_count": len(payload["ts"]),
                    "sdk_payload_sha256": sha256(payload_bytes).hexdigest(),
                    "observed_trade_bearing_minute_count": len(bars),
                    "session_open_source_interval_start_utc": (
                        session_open["source_interval_start_utc"].isoformat()
                    ),
                    "session_open_price": session_open["price"],
                    "first_canonical_minute_start_utc": (
                        bars[0]["bar_start_utc"].isoformat()
                    ),
                    "closing_auction_at_utc": closing["matched_at_utc"].isoformat(),
                    "closing_auction_price": closing["price"],
                    "intervals": interval_results,
                }
            )
            _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass

    summary["status"] = "accepted"
    _write_summary(summary)


def _normalize_payload(payload: dict[str, Any]) -> dict[str, list[int | float]]:
    normalized: dict[str, list[int | float]] = {}
    for field in FIELDS:
        if field not in payload:
            if field == "Amount":
                continue
            raise RuntimeError(f"missing_shioaji_field:{field}")

        values = payload[field]
        if hasattr(values, "tolist"):
            values = values.tolist()
        if not isinstance(values, list):
            values = list(values)

        normalized[field] = [_number(value) for value in values]

    expected_count = len(normalized["ts"])
    if expected_count == 0:
        raise RuntimeError("empty_shioaji_payload")
    if any(len(values) != expected_count for values in normalized.values()):
        raise RuntimeError("inconsistent_shioaji_payload_lengths")
    return normalized


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


def _write_summary(summary: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
