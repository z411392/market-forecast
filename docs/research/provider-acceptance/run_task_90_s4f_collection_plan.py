import json
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)
from libs.market_data.services.build_tick_day_collection_plan import build_tick_day_collection_plan
from libs.market_data.services.partition_tick_day_collection_plan import partition_tick_day_collection_plan

PLAN_VERSION = "task-90-rk-tick-collection-plan-v1"
SYMBOL_ORDER = ("2330", "2317", "2454")
END_SESSION = date(2026, 9, 24)
SESSION_COUNT = 253
MAX_ITEMS = 100
AD_HOC_FULL_DAY_CLOSURES = (date(2026, 7, 10),)
OUTPUT = Path(
    "artifacts/private/provider-captures/task-90-s4f-collection-plan/plan.json"
)

EXPECTED_BATCHES = (
    (1, 99, date(2025, 9, 10), date(2025, 10, 30)),
    (2, 99, date(2025, 10, 31), date(2025, 12, 16)),
    (3, 99, date(2025, 12, 17), date(2026, 2, 3)),
    (4, 99, date(2026, 2, 4), date(2026, 4, 1)),
    (5, 99, date(2026, 4, 2), date(2026, 5, 21)),
    (6, 99, date(2026, 5, 22), date(2026, 7, 8)),
    (7, 99, date(2026, 7, 9), date(2026, 8, 25)),
    (8, 66, date(2026, 8, 26), date(2026, 9, 24)),
)


def main() -> None:
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

    if len(items) != 759:
        raise RuntimeError("s4f_unexpected_plan_item_count")
    if len(batches) != 8:
        raise RuntimeError("s4f_unexpected_batch_count")

    ordered_request_hashes = tuple(
        build_historical_tick_request_sha256(item["request"])
        for item in items
    )
    plan_identity = {
        "plan_version": PLAN_VERSION,
        "symbol_order": list(SYMBOL_ORDER),
        "session_dates": [value.isoformat() for value in sessions],
        "ordered_request_sha256": list(ordered_request_hashes),
    }
    plan_sha256 = _sha256_json(plan_identity)

    batch_records: list[dict[str, Any]] = []
    global_start = 0
    for index, batch in enumerate(batches, start=1):
        request_hashes = tuple(
            build_historical_tick_request_sha256(item["request"])
            for item in batch
        )
        first_session = batch[0]["request"]["session_date"]
        last_session = batch[-1]["request"]["session_date"]
        expected = EXPECTED_BATCHES[index - 1]
        if (
            index != expected[0]
            or len(batch) != expected[1]
            or first_session != expected[2]
            or last_session != expected[3]
        ):
            raise RuntimeError(f"s4f_batch_boundary_mismatch:{index}")

        session_count = len(batch) // len(SYMBOL_ORDER)
        batch_identity = {
            "plan_version": PLAN_VERSION,
            "batch_number": index,
            "global_start_item_index": global_start,
            "global_end_item_index_exclusive": global_start + len(batch),
            "first_session_date": first_session.isoformat(),
            "last_session_date": last_session.isoformat(),
            "session_count": session_count,
            "item_count": len(batch),
            "ordered_request_sha256": list(request_hashes),
        }
        batch_records.append(
            {
                **batch_identity,
                "batch_sha256": _sha256_json(batch_identity),
            }
        )
        global_start += len(batch)

    if global_start != len(items):
        raise RuntimeError("s4f_batch_partition_does_not_cover_plan")

    output = {
        "task": 90,
        "slice": "S4f",
        "status": "accepted",
        "plan_version": PLAN_VERSION,
        "calendar": "XTAI",
        "symbol_order": list(SYMBOL_ORDER),
        "session_count": len(sessions),
        "first_session_date": sessions[0].isoformat(),
        "last_session_date": sessions[-1].isoformat(),
        "ad_hoc_full_day_closures": [
            value.isoformat() for value in AD_HOC_FULL_DAY_CLOSURES
        ],
        "item_count": len(items),
        "planned_max_items_per_batch": 99,
        "collector_hard_max_uncached_acquisitions": MAX_ITEMS,
        "batch_count": len(batch_records),
        "plan_sha256": plan_sha256,
        "ordered_request_sha256": list(ordered_request_hashes),
        "batches": batch_records,
        "first_batch": batch_records[0],
        "resume_rule": (
            "resubmit identical ordered batch; cache-first request SHA identity "
            "determines completed vs uncached items"
        ),
        "provider_calls": 0,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


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
        raise RuntimeError("s4f_unexpected_session_count")
    if sessions[0] != date(2025, 9, 10):
        raise RuntimeError("s4f_unexpected_first_session")
    if sessions[-1] != END_SESSION:
        raise RuntimeError("s4f_unexpected_last_session")
    return sessions


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _sha256_json(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


if __name__ == "__main__":
    main()
