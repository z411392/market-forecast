import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(
    "docs/research/provider-acceptance/"
    "cross-market-rv-measurement-target-manifest-v2.json"
)
US_PATH = Path(
    "artifacts/private/provider-captures/"
    "task-101-us-canonical-panel/daily-values.json"
)
TAIWAN_PATH = Path(
    "artifacts/private/provider-captures/"
    "task-101-taiwan-canonical-panel/daily-values.json"
)
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-101-canonical-panel"
)
PANEL_PATH = OUTPUT_ROOT / "canonical-daily-panel.json"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"

EXPECTED = {
    "GOOGL": {
        "market": "us",
        "provider": "alpaca",
        "calendar": "XNAS",
        "price_basis": "split_adjusted",
        "sampling_minutes": 5,
        "algorithm_version": "rv-core-v1",
    },
    "NVDA": {
        "market": "us",
        "provider": "alpaca",
        "calendar": "XNAS",
        "price_basis": "split_adjusted",
        "sampling_minutes": 5,
        "algorithm_version": "rv-core-v1",
    },
    "QQQ": {
        "market": "us",
        "provider": "alpaca",
        "calendar": "XNAS",
        "price_basis": "split_adjusted",
        "sampling_minutes": 5,
        "algorithm_version": "rv-core-v1",
    },
    "TSM": {
        "market": "us",
        "provider": "alpaca",
        "calendar": "XNAS",
        "price_basis": "split_adjusted",
        "sampling_minutes": 5,
        "algorithm_version": "rv-core-v1",
    },
    "2330": {
        "market": "taiwan",
        "provider": "shioaji",
        "calendar": "XTAI",
        "price_basis": "as_printed",
        "sampling_minutes": 15,
        "algorithm_version": "rv-core-v1+xtai-closing-auction-v4",
    },
    "2317": {
        "market": "taiwan",
        "provider": "shioaji",
        "calendar": "XTAI",
        "price_basis": "as_printed",
        "sampling_minutes": 15,
        "algorithm_version": "rv-core-v1+xtai-closing-auction-v4",
    },
    "2454": {
        "market": "taiwan",
        "provider": "shioaji",
        "calendar": "XTAI",
        "price_basis": "as_printed",
        "sampling_minutes": 15,
        "algorithm_version": "rv-core-v1+xtai-closing-auction-v4",
    },
}
START_DATE = date(2022, 7, 18)
END_DATE = date(2026, 9, 24)


def main() -> None:
    manifest = _load_json(MANIFEST_PATH)
    _validate_manifest(manifest)

    us = _load_json(US_PATH)
    tw = _load_json(TAIWAN_PATH)
    _validate_source_metadata(us, "us")
    _validate_source_metadata(tw, "taiwan")

    daily_values: dict[str, Any] = {}
    symbols_summary: list[dict[str, Any]] = []

    for symbol, identity in EXPECTED.items():
        source = us if identity["market"] == "us" else tw
        raw_rows = source["daily_values"].get(symbol)
        if not isinstance(raw_rows, list):
            raise RuntimeError(
                f"task101_missing_symbol_rows:{symbol}"
            )
        rows = _validate_rows(symbol, raw_rows)
        daily_values[symbol] = {
            "market": identity["market"],
            "provider": identity["provider"],
            "calendar": identity["calendar"],
            "price_basis": identity["price_basis"],
            "sampling_minutes": identity["sampling_minutes"],
            "algorithm_version": identity["algorithm_version"],
            "rows": rows,
        }
        measured_variances = [
            row["whole_day_variance"]
            for row in rows
            if row["whole_day_variance"] is not None
        ]
        if not measured_variances:
            raise RuntimeError(
                f"task101_no_measured_variance:{symbol}"
            )
        symbols_summary.append(
            {
                "symbol": symbol,
                "market": identity["market"],
                "session_count": len(rows),
                "measured_session_count": len(measured_variances),
                "missing_measurement_count": (
                    len(rows) - len(measured_variances)
                ),
                "first_session": rows[0]["session_date"],
                "last_session": rows[-1]["session_date"],
                "min_whole_day_variance": min(measured_variances),
                "max_whole_day_variance": max(measured_variances),
            }
        )

    panel = {
        "artifact_version": "task-101-canonical-daily-panel-v1",
        "task": 101,
        "measurement_manifest_version": manifest[
            "artifact_version"
        ],
        "measurement_frozen": manifest["measurement_frozen"],
        "target_version": manifest["target"]["target_version"],
        "primary_horizon_sessions": manifest["target"][
            "primary_horizon_sessions"
        ],
        "confirmatory_horizon_sessions": manifest["target"][
            "confirmatory_horizon_sessions"
        ],
        "study_start": START_DATE.isoformat(),
        "study_end": END_DATE.isoformat(),
        "input_sha256": {
            "us_daily_values": _sha256(US_PATH),
            "taiwan_daily_values": _sha256(TAIWAN_PATH),
            "measurement_manifest": _sha256(MANIFEST_PATH),
        },
        "daily_values": daily_values,
    }
    _write_json(PANEL_PATH, panel)

    summary = {
        "task": 101,
        "slice": "S1-canonical-panel-merge",
        "status": "accepted",
        "panel_sha256": _sha256(PANEL_PATH),
        "input_sha256": panel["input_sha256"],
        "symbols": symbols_summary,
        "market_session_counts": {
            "us": sorted(
                {
                    item["session_count"]
                    for item in symbols_summary
                    if item["market"] == "us"
                }
            ),
            "taiwan": sorted(
                {
                    item["session_count"]
                    for item in symbols_summary
                    if item["market"] == "taiwan"
                }
            ),
        },
    }
    if len(summary["market_session_counts"]["us"]) != 1:
        raise RuntimeError(
            "task101_us_symbol_session_count_mismatch"
        )
    if len(summary["market_session_counts"]["taiwan"]) != 1:
        raise RuntimeError(
            "task101_tw_symbol_session_count_mismatch"
        )
    _write_json(SUMMARY_PATH, summary)


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if (
        manifest.get("artifact_version")
        != "cross-market-rv-measurement-target-manifest-v2"
        or manifest.get("measurement_frozen") is not True
    ):
        raise RuntimeError("task101_invalid_measurement_manifest")

    us = manifest["markets"]["US"]
    tw = manifest["markets"]["Taiwan"]
    expected_pairs = (
        (
            us,
            {
                "canonical_sampling_minutes": 5,
                "price_basis": "split_adjusted",
                "algorithm_version": "rv-core-v1",
                "provider": "alpaca",
                "calendar": "XNAS",
            },
        ),
        (
            tw,
            {
                "canonical_sampling_minutes": 15,
                "price_basis": "as_printed",
                "algorithm_version": (
                    "rv-core-v1+xtai-closing-auction-v4"
                ),
                "provider": "shioaji",
                "calendar": "XTAI",
            },
        ),
    )
    for actual, expected in expected_pairs:
        for key, value in expected.items():
            if actual.get(key) != value:
                raise RuntimeError(
                    f"task101_manifest_identity_mismatch:{key}"
                )


def _validate_source_metadata(
    source: dict[str, Any],
    market: str,
) -> None:
    if source.get("task") != 101:
        raise RuntimeError("task101_source_task_mismatch")
    if source.get("first_panel_session") != START_DATE.isoformat():
        raise RuntimeError(
            f"task101_{market}_start_mismatch"
        )
    if source.get("last_panel_session") != END_DATE.isoformat():
        raise RuntimeError(
            f"task101_{market}_end_mismatch"
        )

    sample_symbol = (
        "GOOGL" if market == "us" else "2330"
    )
    expected = EXPECTED[sample_symbol]
    for key in (
        "provider",
        "calendar",
        "price_basis",
        "sampling_minutes",
        "algorithm_version",
    ):
        if source.get(key) != expected[key]:
            raise RuntimeError(
                f"task101_{market}_metadata_mismatch:{key}"
            )


def _validate_rows(
    symbol: str,
    raw_rows: list[object],
) -> list[dict[str, Any]]:
    if not raw_rows:
        raise RuntimeError(f"task101_empty_symbol_rows:{symbol}")

    rows: list[dict[str, Any]] = []
    previous_date: date | None = None
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise RuntimeError(
                f"task101_invalid_symbol_row:{symbol}"
            )
        session_date = date.fromisoformat(
            _require_str(raw.get("session_date"))
        )
        if session_date < START_DATE or session_date > END_DATE:
            raise RuntimeError(
                f"task101_session_outside_window:{symbol}"
            )
        if previous_date is not None and session_date <= previous_date:
            raise RuntimeError(
                f"task101_non_increasing_session:{symbol}"
            )
        previous_date = session_date

        raw_variance = raw.get("whole_day_variance")
        if raw_variance is None:
            missing_reason = _require_str(
                raw.get("missing_reason")
            )
            if (
                raw.get("regular_session_variance") is not None
                or raw.get("observation_count") != 0
            ):
                raise RuntimeError(
                    f"task101_invalid_missing_measurement:{symbol}"
                )
            raw_overnight = raw.get("overnight_variance")
            overnight = (
                None
                if raw_overnight is None
                else _nonnegative_finite(
                    raw_overnight,
                    f"task101_invalid_missing_overnight:{symbol}",
                )
            )
            rows.append(
                {
                    "session_date": session_date.isoformat(),
                    "whole_day_variance": None,
                    "regular_session_variance": None,
                    "overnight_variance": overnight,
                    "observation_count": 0,
                    "missing_reason": missing_reason,
                }
            )
            continue

        variance = _positive_finite(
            raw_variance,
            f"task101_invalid_variance:{symbol}",
        )
        regular = _nonnegative_finite(
            raw.get("regular_session_variance"),
            f"task101_invalid_regular_variance:{symbol}",
        )
        overnight = _nonnegative_finite(
            raw.get("overnight_variance"),
            f"task101_invalid_overnight_variance:{symbol}",
        )
        if not math.isclose(
            regular + overnight,
            variance,
            rel_tol=1e-11,
            abs_tol=1e-15,
        ):
            raise RuntimeError(
                f"task101_variance_identity_mismatch:{symbol}"
            )

        rows.append(
            {
                "session_date": session_date.isoformat(),
                "whole_day_variance": variance,
                "regular_session_variance": regular,
                "overnight_variance": overnight,
                "observation_count": _positive_int(
                    raw.get("observation_count"),
                    f"task101_invalid_observation_count:{symbol}",
                ),
                "missing_reason": None,
            }
        )

    if rows[0]["session_date"] != START_DATE.isoformat():
        raise RuntimeError(
            f"task101_symbol_first_session_mismatch:{symbol}"
        )
    if rows[-1]["session_date"] != END_DATE.isoformat():
        raise RuntimeError(
            f"task101_symbol_last_session_mismatch:{symbol}"
        )
    return rows


def _positive_finite(value: object, error: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise RuntimeError(error)
    return float(value)


def _nonnegative_finite(
    value: object,
    error: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise RuntimeError(error)
    return float(value)


def _positive_int(value: object, error: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeError(error)
    return value


def _require_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("task101_invalid_string")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("task101_json_not_object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
