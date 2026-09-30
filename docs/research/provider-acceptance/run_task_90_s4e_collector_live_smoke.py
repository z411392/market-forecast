import json
import os
import shutil
from datetime import date, time
from pathlib import Path
from typing import Any

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
from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_batch_collection_summary import (
    TickBatchCollectionSummary,
)
from libs.market_data.dtos.tick_day_collection_item import TickDayCollectionItem
from libs.market_data.ports.fetch_historical_tick_payload_port import (
    FetchHistoricalTickPayloadPort,
)
from libs.market_data.ports.read_provider_traffic_usage_port import (
    ReadProviderTrafficUsagePort,
)
from libs.market_data.services.collect_tick_day_evidence_batch import (
    collect_tick_day_evidence_batch,
)

CASES = (
    ("2330", date(2026, 9, 24), "active_normal_reference"),
    ("2317", date(2026, 9, 24), "normal_reference"),
    ("2454", date(2026, 5, 4), "locked_limit_low_activity"),
)
TIME_START = time(9, 0, 0)
TIME_END = time(13, 30, 59)
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-90-s4e-collector-live-smoke"
)
CACHE_ROOT = OUTPUT_ROOT / "cache"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"


class CountingFetch(FetchHistoricalTickPayloadPort):
    def __init__(self, delegate: FetchHistoricalTickPayloadPort) -> None:
        self._delegate = delegate
        self.calls = 0

    def __call__(self, request: HistoricalTickRequestSpec) -> Any:
        self.calls += 1
        return self._delegate(request)


class CountingUsage(ReadProviderTrafficUsagePort):
    def __init__(self, delegate: ReadProviderTrafficUsagePort) -> None:
        self._delegate = delegate
        self.calls = 0

    def __call__(self) -> Any:
        self.calls += 1
        return self._delegate()


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret("MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    items = _build_items()
    summary: dict[str, Any] = {
        "task": 90,
        "slice": "S4e",
        "smoke_version": "task-90-s4e-collector-live-smoke-v1",
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "cases": [
            {
                "symbol": symbol,
                "session_date": session_date.isoformat(),
                "role": role,
            }
            for symbol, session_date, role in CASES
        ],
        "status": "running",
    }
    _write_summary(summary)

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )

        store = FilesystemTickDayEvidenceAdapter(CACHE_ROOT)

        first_fetch = CountingFetch(
            ShioajiHistoricalTickPayloadAdapter(
                api,
                range_time_query_type=sj.constant.TicksQueryType.RangeTime,
                timeout_ms=15000,
            )
        )
        first_usage = CountingUsage(ShioajiProviderTrafficUsageAdapter(api))

        first = collect_tick_day_evidence_batch(
            items=items,
            fetch_payload=first_fetch,
            read_usage=first_usage,
            evidence_store=store,
            provider_version=sj.__version__,
        )
        _assert_first_pass(first, first_fetch.calls)
        first_receipts = tuple(first["receipts"])

        summary["first_pass"] = _serialize_batch(
            first,
            fetch_calls=first_fetch.calls,
            usage_calls=first_usage.calls,
        )
        summary["persisted_evidence"] = _persisted_evidence_summary(first_receipts)
        _write_summary(summary)

        second_fetch = CountingFetch(
            ShioajiHistoricalTickPayloadAdapter(
                api,
                range_time_query_type=sj.constant.TicksQueryType.RangeTime,
                timeout_ms=15000,
            )
        )
        second_usage = CountingUsage(ShioajiProviderTrafficUsageAdapter(api))

        second = collect_tick_day_evidence_batch(
            items=items,
            fetch_payload=second_fetch,
            read_usage=second_usage,
            evidence_store=store,
            provider_version=sj.__version__,
        )
        _assert_second_pass(
            second,
            first_receipts=first_receipts,
            fetch_calls=second_fetch.calls,
            usage_calls=second_usage.calls,
        )

        summary["second_pass"] = _serialize_batch(
            second,
            fetch_calls=second_fetch.calls,
            usage_calls=second_usage.calls,
        )
        summary["cache_resume_receipts_equal"] = (
            tuple(second["receipts"]) == first_receipts
        )
        summary["status"] = "accepted"
        _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass


def _build_items() -> tuple[TickDayCollectionItem, ...]:
    items: list[TickDayCollectionItem] = []
    for symbol, session_date, _role in CASES:
        request: HistoricalTickRequestSpec = {
            "provider": "shioaji",
            "source_symbol": symbol,
            "session_date": session_date,
            "query_type": "RangeTime",
            "time_start_local": TIME_START,
            "time_end_local": TIME_END,
        }
        security: SecurityIdentity = {
            "symbol": symbol,
            "exchange": "XTAI",
            "timezone": "Asia/Taipei",
            "calendar_id": "XTAI",
        }
        items.append(
            {
                "request": request,
                "security": security,
            }
        )
    return tuple(items)


def _assert_first_pass(
    result: TickBatchCollectionSummary,
    fetch_calls: int,
) -> None:
    if result["requested_count"] != 3:
        raise RuntimeError("s4e_first_pass_unexpected_requested_count")
    if result["cache_hit_count"] != 0:
        raise RuntimeError("s4e_first_pass_unexpected_cache_hit")
    if result["acquired_count"] != 3:
        raise RuntimeError("s4e_first_pass_unexpected_acquired_count")
    if result["deferred_count"] != 0:
        raise RuntimeError("s4e_first_pass_unexpected_deferred_count")
    if result["stop_reason"] != "completed":
        raise RuntimeError("s4e_first_pass_not_completed")
    if fetch_calls != 3:
        raise RuntimeError("s4e_first_pass_fetch_count_mismatch")
    if len(result["receipts"]) != 3:
        raise RuntimeError("s4e_first_pass_receipt_count_mismatch")


def _assert_second_pass(
    result: TickBatchCollectionSummary,
    *,
    first_receipts: tuple[Any, ...],
    fetch_calls: int,
    usage_calls: int,
) -> None:
    if result["requested_count"] != 3:
        raise RuntimeError("s4e_second_pass_unexpected_requested_count")
    if result["cache_hit_count"] != 3:
        raise RuntimeError("s4e_second_pass_cache_hits_not_three")
    if result["acquired_count"] != 0:
        raise RuntimeError("s4e_second_pass_acquired_nonzero")
    if result["deferred_count"] != 0:
        raise RuntimeError("s4e_second_pass_deferred_nonzero")
    if result["stop_reason"] != "completed":
        raise RuntimeError("s4e_second_pass_not_completed")
    if fetch_calls != 0:
        raise RuntimeError("s4e_second_pass_provider_fetch_occurred")
    if usage_calls != 0:
        raise RuntimeError("s4e_second_pass_provider_usage_call_occurred")
    if result["initial_usage"] is not None or result["final_usage"] is not None:
        raise RuntimeError("s4e_second_pass_usage_state_not_empty")
    if tuple(result["receipts"]) != first_receipts:
        raise RuntimeError("s4e_second_pass_receipts_changed")


def _serialize_batch(
    result: TickBatchCollectionSummary,
    *,
    fetch_calls: int,
    usage_calls: int,
) -> dict[str, Any]:
    return {
        "requested_count": result["requested_count"],
        "cache_hit_count": result["cache_hit_count"],
        "acquired_count": result["acquired_count"],
        "deferred_count": result["deferred_count"],
        "stop_reason": result["stop_reason"],
        "fetch_calls": fetch_calls,
        "usage_calls": usage_calls,
        "current_run_delta_bytes": result["current_run_delta_bytes"],
        "initial_usage": result["initial_usage"],
        "final_usage": result["final_usage"],
        "receipts": [_serialize_receipt(receipt) for receipt in result["receipts"]],
    }


def _persisted_evidence_summary(receipts: tuple[Any, ...]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for receipt in receipts:
        evidence_dir = CACHE_ROOT / "shioaji" / receipt["request_sha256"]
        expected = (
            evidence_dir / "sdk-observation.json",
            evidence_dir / "transactions.json",
            evidence_dir / "receipt.json",
        )
        if not all(path.is_file() for path in expected):
            raise RuntimeError("s4e_persisted_evidence_file_missing")
        output.append(
            {
                "symbol": receipt["source_symbol"],
                "session_date": receipt["session_date"].isoformat(),
                "request_sha256": receipt["request_sha256"],
                "sdk_observation_sha256": receipt["sdk_observation_sha256"],
                "transaction_sequence_sha256": receipt[
                    "transaction_sequence_sha256"
                ],
                "tick_count": receipt["tick_count"],
                "evidence_dir": str(evidence_dir),
            }
        )
    return output


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
