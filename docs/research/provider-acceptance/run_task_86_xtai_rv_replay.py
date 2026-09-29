import json
import math
import os
from datetime import date, datetime, timezone
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
    ("2454", date(2026, 5, 4), "empty_5m_bucket_blocker"),
    ("2317", date(2025, 11, 17), "delayed_open_reference"),
    ("2317", date(2026, 9, 24), "normal_open_reference"),
    ("2330", date(2024, 7, 2), "frozen_ordinary_reference"),
    ("2330", date(2026, 9, 24), "frozen_parity_reference"),
)
OUTPUT = Path("artifacts/private/provider-captures/task-86-xtai-rv/summary.json")
FIELDS = ("ts", "Open", "High", "Low", "Close", "Volume", "Amount")

EXPECTED_V3_RV = {
    ("2317", "2025-11-17", 5): 0.0005654172179537024,
    ("2317", "2025-11-17", 10): 0.00032639986742110836,
    ("2317", "2025-11-17", 15): 0.0004428205189068247,
    ("2317", "2026-09-24", 5): 0.00013091528840799728,
    ("2317", "2026-09-24", 10): 0.00013074199229837273,
    ("2317", "2026-09-24", 15): 0.0001147259495782424,
    ("2330", "2024-07-02", 5): 0.00010221288319299749,
    ("2330", "2024-07-02", 10): 8.706959301028129e-05,
    ("2330", "2024-07-02", 15): 0.00013856332496125267,
    ("2330", "2026-09-24", 5): 0.00010964302898558377,
    ("2330", "2026-09-24", 10): 5.283407680026145e-05,
    ("2330", "2026-09-24", 15): 3.659131792395245e-05,
}

BLOCKER_BOUNDARY_UTC = datetime(2026, 5, 4, 3, 30, tzinfo=timezone.utc)
BLOCKER_SOURCE_START_UTC = datetime(2026, 5, 4, 3, 23, tzinfo=timezone.utc)
BLOCKER_SOURCE_END_UTC = datetime(2026, 5, 4, 3, 24, tzinfo=timezone.utc)


def main() -> None:
    api_key = os.environ.get("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = os.environ.get("MARKET_FORECAST_SHIOAJI_SECRET_KEY")
    if api_key is None or not api_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_API_KEY")
    if secret_key is None or not secret_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    summary: dict[str, Any] = {
        "task": 86,
        "replay_version": "xtai-previous-tick-v4-live-replay-v1",
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
                        "unexpected_observation_count:"
                        f"{symbol}:{session_date}:{interval}"
                    )
                if len(sampled) != expected_observation_count:
                    raise RuntimeError(
                        "unexpected_sampled_price_count:"
                        f"{symbol}:{session_date}:{interval}"
                    )
                if (
                    measures["algorithm_version"]
                    != XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION
                ):
                    raise RuntimeError(
                        "unexpected_algorithm_version:"
                        f"{symbol}:{session_date}:{interval}"
                    )

                expected_v3 = EXPECTED_V3_RV.get(
                    (symbol, session_date.isoformat(), interval)
                )
                if expected_v3 is not None and not math.isclose(
                    measures["realized_variance"],
                    expected_v3,
                    rel_tol=1e-12,
                    abs_tol=1e-15,
                ):
                    raise RuntimeError(
                        "reference_numeric_drift:"
                        f"{symbol}:{session_date}:{interval}:"
                        f"{measures['realized_variance']}:{expected_v3}"
                    )

                previous_tick_samples = [
                    _sample_provenance(sample)
                    for sample in sampled
                    if sample["observation_mode"] == "previous_tick"
                ]

                if (
                    symbol == "2454"
                    and session_date == date(2026, 5, 4)
                    and interval == 5
                ):
                    _assert_2454_blocker_sample(sampled)

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
                        "previous_tick_sample_count": len(previous_tick_samples),
                        "previous_tick_samples": previous_tick_samples,
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


def _assert_2454_blocker_sample(samples: tuple[dict[str, Any], ...]) -> None:
    blocker = next(
        (
            sample
            for sample in samples
            if sample["observed_at_utc"] == BLOCKER_BOUNDARY_UTC
        ),
        None,
    )
    if blocker is None:
        raise RuntimeError("missing_2454_1130_sample")
    if blocker["observation_mode"] != "previous_tick":
        raise RuntimeError("2454_1130_not_previous_tick")
    if blocker["price"] != 2870.0:
        raise RuntimeError("unexpected_2454_1130_price")
    if blocker["source_interval_start_utc"] != BLOCKER_SOURCE_START_UTC:
        raise RuntimeError("unexpected_2454_1130_source_start")
    if blocker["source_interval_end_utc"] != BLOCKER_SOURCE_END_UTC:
        raise RuntimeError("unexpected_2454_1130_source_end")
    if blocker["staleness_lower_bound_seconds"] != 360.0:
        raise RuntimeError("unexpected_2454_1130_staleness_lower")
    if blocker["staleness_upper_bound_seconds"] != 420.0:
        raise RuntimeError("unexpected_2454_1130_staleness_upper")


def _sample_provenance(sample: dict[str, Any]) -> dict[str, object]:
    return {
        "observed_at_utc": sample["observed_at_utc"].isoformat(),
        "price": sample["price"],
        "source_interval_start_utc": sample["source_interval_start_utc"].isoformat(),
        "source_interval_end_utc": sample["source_interval_end_utc"].isoformat(),
        "observation_mode": sample["observation_mode"],
        "staleness_lower_bound_seconds": sample["staleness_lower_bound_seconds"],
        "staleness_upper_bound_seconds": sample["staleness_upper_bound_seconds"],
    }


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
