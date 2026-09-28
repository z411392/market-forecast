from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Task #63 FinMind 2330 TradingView parity reference."
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    return parser.parse_args()


def _expected_request(session_date: str) -> dict[str, object]:
    return {
        "method": "GET",
        "path": "/api/v4/data",
        "query": [
            ["dataset", "TaiwanStockKBar"],
            ["data_id", "2330"],
            ["start_date", session_date],
        ],
    }


def main() -> None:
    args = _parse_args()
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    source_bytes = args.source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()

    tv = reference["tradingview_reference"]
    if source_sha != tv["sha256"]:
        raise AssertionError(f"source SHA mismatch: {source_sha}")

    with args.source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = tuple(reader)
        fieldnames = tuple(reader.fieldnames or ())

    if len(rows) != tv["row_count"]:
        raise AssertionError(f"row count mismatch: {len(rows)}")
    if len(fieldnames) != tv["column_count"]:
        raise AssertionError(f"column count mismatch: {len(fieldnames)}")

    required = {"time", "P4_INTRABAR_COUNT_5M", "P4_RV_WHOLE_DAY_5M"}
    missing = required.difference(fieldnames)
    if missing:
        raise AssertionError(f"missing columns: {sorted(missing)}")

    by_date: dict[str, dict[str, str]] = {}
    for row in rows:
        session_date = datetime.fromtimestamp(
            int(float(row["time"])),
            tz=timezone.utc,
        ).date().isoformat()
        by_date[session_date] = row

    if max(by_date) != tv["latest_session_date"]:
        raise AssertionError(f"latest session mismatch: {max(by_date)}")

    for name in ("ordinary", "parity"):
        session = reference["sessions"][name]
        session_date = session["session_date"]
        row = by_date.get(session_date)
        if row is None:
            raise AssertionError(f"{name}: missing source session {session_date}")

        count = int(float(row["P4_INTRABAR_COUNT_5M"]))
        if count != session["tradingview_intrabar_count_5m"]:
            raise AssertionError(f"{name}: intrabar count mismatch {count}")

        rv = float(row["P4_RV_WHOLE_DAY_5M"])
        expected_rv = float(session["tradingview_whole_day_rv_5m"])
        if not math.isclose(rv, expected_rv, rel_tol=0.0, abs_tol=1e-15):
            raise AssertionError(f"{name}: RV mismatch {rv} != {expected_rv}")

        if session["request"] != _expected_request(session_date):
            raise AssertionError(f"{name}: request spec mismatch")

    authorization = reference["authorization"]
    if any(authorization.values()):
        raise AssertionError("live/provider authorization must remain false in Task #63")

    print(
        "PASS: FinMind 2330 acceptance reference "
        f"({tv['row_count']} rows, latest={tv['latest_session_date']})"
    )


if __name__ == "__main__":
    main()
