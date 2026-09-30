import json
import os
import shutil
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import shioaji as sj

from libs.market_data.adapters.driven.filesystem_tick_day_evidence_adapter import (
    FilesystemTickDayEvidenceAdapter,
)
from libs.market_data.adapters.driven.shioaji_historical_tick_payload_adapter import (
    ShioajiHistoricalTickPayloadAdapter,
)
from libs.market_data.adapters.driven.shioaji_provider_traffic_usage_adapter import (
    ShioajiProviderTrafficUsageAdapter,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)
from libs.market_data.services.build_tick_day_collection_plan import build_tick_day_collection_plan
from libs.market_data.services.collect_tick_day_evidence_batch import (
    collect_tick_day_evidence_batch,
)
from libs.market_data.services.partition_tick_day_collection_plan import (
    partition_tick_day_collection_plan,
)

PLAN_VERSION = "task-90-rk-tick-collection-plan-v1"
SYMBOL_ORDER = ("2330", "2317", "2454")
END_SESSION = date(2026, 9, 24)
SESSION_COUNT = 253
MAX_ITEMS = 100
AD_HOC_FULL_DAY_CLOSURES = (date(2026, 7, 10),)

REQUEST_PATH = Path(
    "docs/research/provider-acceptance/task-90-s4g-live-batch-request.json"
)
REFERENCE_PATH = Path(
    "docs/research/provider-acceptance/task-90-s4f-collection-plan-reference.json"
)
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-90-s4g-live-batch"
)
CACHE_ROOT = OUTPUT_ROOT / "cache"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"


def main() -> None:
    request = _load_json(REQUEST_PATH)
    reference = _load_json(REFERENCE_PATH)
    batch_number = _require_batch_number(request)

    sessions = _actual_sessions()
    securities = tuple(_security(symbol) for symbol in SYMBOL_ORDER)
    items = build_tick_day_collection_plan(
        session_dates=sessions,
        securities=securities,
    )
    batches = partition_tick_day_collection_plan(
        items=items,
        symbols_per_session=len(SYMBOL_ORDER),
        max_items=MAX_ITEMS,
    )
    if len(items) != 759 or len(batches) != 8:
        raise RuntimeError("s4g_frozen_plan_shape_changed")

    batch = batches[batch_number - 1]
    reference_batch = reference["batches"][batch_number - 1]
    computed_identity = _build_batch_identity(
        batch_number=batch_number,
        batch=batch,
        batches=batches,
    )
    computed_sha256 = _sha256_json(computed_identity)

    if reference["plan_version"] != PLAN_VERSION:
        raise RuntimeError("s4g_reference_plan_version_changed")
    if reference_batch["batch_number"] != batch_number:
        raise RuntimeError("s4g_reference_batch_number_mismatch")
    if computed_sha256 != reference_batch["batch_sha256"]:
        raise RuntimeError("s4g_batch_identity_mismatch")
    if request["expected_batch_sha256"] != computed_sha256:
        raise RuntimeError("s4g_request_batch_sha256_mismatch")
    if request.get("authorized") is not True:
        raise RuntimeError("s4g_live_batch_not_authorized")

    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret("MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "task": 90,
        "slice": "S4g",
        "status": "running",
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "batch_number": batch_number,
        "batch_sha256": computed_sha256,
        "item_count": len(batch),
        "first_session_date": batch[0]["request"]["session_date"].isoformat(),
        "last_session_date": batch[-1]["request"]["session_date"].isoformat(),
    }
    _write_summary(summary)

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )
        result = collect_tick_day_evidence_batch(
            items=batch,
            fetch_payload=ShioajiHistoricalTickPayloadAdapter(
                api,
                range_time_query_type=sj.constant.TicksQueryType.RangeTime,
                timeout_ms=15000,
            ),
            read_usage=ShioajiProviderTrafficUsageAdapter(api),
            evidence_store=FilesystemTickDayEvidenceAdapter(CACHE_ROOT),
            provider_version=sj.__version__,
        )

        summary["collection"] = {
            "requested_count": result["requested_count"],
            "cache_hit_count": result["cache_hit_count"],
            "acquired_count": result["acquired_count"],
            "deferred_count": result["deferred_count"],
            "stop_reason": result["stop_reason"],
            "current_run_delta_bytes": result["current_run_delta_bytes"],
            "initial_usage": result["initial_usage"],
            "final_usage": result["final_usage"],
            "receipts": [
                _serialize_receipt(receipt)
                for receipt in result["receipts"]
            ],
        }

        if (
            result["requested_count"] != len(batch)
            or result["deferred_count"] != 0
            or result["stop_reason"] != "completed"
            or len(result["receipts"]) != len(batch)
        ):
            summary["status"] = "partial_guard_stop"
            _write_summary(summary)
            raise RuntimeError("s4g_batch_not_completed")

        summary["status"] = "accepted"
        _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass


def _build_batch_identity(
    *,
    batch_number: int,
    batch: tuple[Any, ...],
    batches: tuple[tuple[Any, ...], ...],
) -> dict[str, Any]:
    global_start = sum(len(value) for value in batches[: batch_number - 1])
    request_hashes = [
        build_historical_tick_request_sha256(item["request"])
        for item in batch
    ]
    return {
        "plan_version": PLAN_VERSION,
        "batch_number": batch_number,
        "global_start_item_index": global_start,
        "global_end_item_index_exclusive": global_start + len(batch),
        "first_session_date": batch[0]["request"]["session_date"].isoformat(),
        "last_session_date": batch[-1]["request"]["session_date"].isoformat(),
        "session_count": len(batch) // len(SYMBOL_ORDER),
        "item_count": len(batch),
        "ordered_request_sha256": request_hashes,
    }


def _actual_sessions() -> tuple[date, ...]:
    calendar = xcals.get_calendar("XTAI")
    scheduled = tuple(
        timestamp.date()
        for timestamp in calendar.sessions_window(
            END_SESSION.isoformat(),
            -(SESSION_COUNT + 10),
        )
    )
    adjusted = tuple(
        session_date
        for session_date in scheduled
        if session_date not in AD_HOC_FULL_DAY_CLOSURES
    )
    sessions = adjusted[-SESSION_COUNT:]
    if len(sessions) != SESSION_COUNT:
        raise RuntimeError("s4g_unexpected_session_count")
    if sessions[0] != date(2025, 9, 10) or sessions[-1] != END_SESSION:
        raise RuntimeError("s4g_session_window_changed")
    return sessions


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _require_batch_number(request: dict[str, Any]) -> int:
    value = request.get("batch_number")
    if type(value) is not int or value < 1 or value > 8:
        raise RuntimeError("s4g_invalid_batch_number")
    return value


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _serialize_receipt(receipt: Any) -> dict[str, Any]:
    return {
        "provider": receipt["provider"],
        "provider_version": receipt["provider_version"],
        "source_symbol": receipt["source_symbol"],
        "session_date": receipt["session_date"].isoformat(),
        "request_sha256": receipt["request_sha256"],
        "sdk_observation_sha256": receipt["sdk_observation_sha256"],
        "transaction_sequence_sha256": receipt["transaction_sequence_sha256"],
        "estimator_version": receipt["estimator_version"],
        "tick_count": receipt["tick_count"],
        "first_observed_at_utc": receipt["first_observed_at_utc"].isoformat(),
        "last_observed_at_utc": receipt["last_observed_at_utc"].isoformat(),
        "opening_price": receipt["opening_price"],
        "closing_auction_observed_at_utc": receipt[
            "closing_auction_observed_at_utc"
        ].isoformat(),
        "closing_auction_price": receipt["closing_auction_price"],
        "duplicate_timestamp_adjacency_count": receipt[
            "duplicate_timestamp_adjacency_count"
        ],
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("s4g_invalid_json_object")
    return value


def _sha256_json(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _write_summary(summary: dict[str, Any]) -> None:
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
