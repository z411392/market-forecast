import argparse
import json
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(
    "docs/research/provider-acceptance/"
    "cross-market-rv-measurement-target-manifest-v2.json"
)
US_REFERENCE_PATH = Path(
    "docs/research/provider-acceptance/"
    "task-106-us-bandi-russell-final-reference.json"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--taiwan-reference",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    manifest = _load(MANIFEST_PATH)
    us_reference = _load(US_REFERENCE_PATH)
    taiwan_reference = _load(args.taiwan_reference)

    _verify_top_level(manifest)
    _verify_us(manifest["markets"]["US"], us_reference)
    _verify_taiwan(
        manifest["markets"]["Taiwan"],
        taiwan_reference,
    )
    _verify_target(manifest["target"])


def _verify_top_level(manifest: dict[str, Any]) -> None:
    assert (
        manifest["artifact_version"]
        == "cross-market-rv-measurement-target-manifest-v2"
    )
    assert manifest["status"] == "frozen"
    assert manifest["measurement_frozen"] is True
    assert (
        manifest["forecast_score_used_for_measurement_selection"]
        is False
    )
    assert (
        manifest["supersedes"]["artifact_version"]
        == "cross-market-rv-measurement-target-manifest-v1"
    )
    invariants = manifest["cross_market_invariants"]
    assert invariants["whole_day_measurement"] is True
    assert invariants["overnight_variance_included"] is True
    assert (
        invariants[
            "future_target_is_average_variance_not_volatility"
        ]
        is True
    )
    assert (
        invariants["no_forecast_qlike_in_measurement_selection"]
        is True
    )


def _verify_us(
    market: dict[str, Any],
    reference: dict[str, Any],
) -> None:
    assert reference["status"] == "accepted_final"
    ruling = reference["ruling"]
    assert ruling["us_canonical_sampling"] == "5m"
    assert ruling["forecast_score_used"] is False
    assert ruling["transaction_tick_full_panel_required"] is False

    primary = reference["primary_panel"]
    assert primary["decision_gate_passed"] is True
    assert primary["audit_sessions_per_symbol"] == 252
    assert primary["symbols"] == ["AAPL", "NVDA"]
    assert (
        primary["first_audit_session"] == "2024-09-19"
    )
    assert primary["last_audit_session"] == "2025-09-22"
    for symbol in ("AAPL", "NVDA"):
        result = primary["results"][symbol]
        assert result["symbol_candidate"] == "5m"
        assert result["support_consistent"] is True

    replication = reference["replication_panel"]
    assert replication["replication_candidate"] == "5m"
    assert replication["audit_sessions_per_symbol"] == 252
    for symbol in ("AAPL", "NVDA"):
        result = replication["results"][symbol]
        assert result["symbol_candidate"] == "5m"
        assert result["support_consistent"] is True

    assert market["canonical_sampling_minutes"] == 5
    assert market["price_basis"] == "split_adjusted"
    assert market["algorithm_version"] == "rv-core-v1"
    assert market["provider"] == "alpaca"
    decision = market["measurement_decision"]
    assert decision["task"] == 106
    assert decision["ruling"] == "US_CANONICAL_SAMPLING = 5m"
    assert decision["forecast_score_used"] is False

    manifest_primary = decision["primary_panel"]
    assert (
        manifest_primary["artifact_sha256"]
        == primary["artifact_sha256"]
    )
    assert (
        manifest_primary["summary_sha256"]
        == primary["summary_sha256"]
    )
    assert (
        manifest_primary["daily_values_sha256"]
        == primary["daily_values_sha256"]
    )
    assert (
        manifest_primary["decision_gate_passed"]
        == primary["decision_gate_passed"]
    )

    manifest_replication = decision["replication_panel"]
    assert (
        manifest_replication["artifact_sha256"]
        == replication["artifact_sha256"]
    )
    assert (
        manifest_replication["summary_sha256"]
        == replication["summary_sha256"]
    )
    assert (
        manifest_replication["daily_values_sha256"]
        == replication["daily_values_sha256"]
    )
    assert (
        manifest_replication["replication_candidate"]
        == replication["replication_candidate"]
    )


def _verify_taiwan(
    market: dict[str, Any],
    reference: dict[str, Any],
) -> None:
    assert reference["status"] == "accepted_final"
    decision_reference = reference["decision"]
    assert (
        decision_reference["taiwan_canonical_sampling"]
        == "15m"
    )
    assert decision_reference["forecast_score_used"] is False
    assert market["canonical_sampling_minutes"] == 15
    assert market["price_basis"] == "as_printed"
    assert (
        market["algorithm_version"]
        == "rv-core-v1+xtai-closing-auction-v4"
    )
    assert market["provider"] == "shioaji"

    decision = market["measurement_decision"]
    assert decision["task"] == 90
    assert decision["ruling"] == "TAIWAN_CANONICAL_SAMPLING = 15m"
    assert decision["forecast_score_used"] is False
    final_workflow = reference["final_workflow"]
    assert decision["run_id"] == final_workflow["run_id"]
    assert decision["artifact_id"] == final_workflow["artifact_id"]
    assert (
        decision["artifact_sha256"]
        == final_workflow["artifact_sha256"]
    )
    assert (
        decision["summary_sha256"]
        == final_workflow["summary_sha256"]
    )


def _verify_target(target: dict[str, Any]) -> None:
    assert target["target_name"] == "future_average_whole_day_variance"
    assert target["target_version"] == "whole_day_variance_v1"
    assert target["unit"] == "log_return_variance"
    assert target["primary_horizon_sessions"] == 5
    assert target["confirmatory_horizon_sessions"] == 20
    assert target["origin_session_included"] is False
    assert target["first_target_session_offset"] == 1
    assert (
        target["missing_session_behavior"]
        == "fail_closed_do_not_compress_horizon"
    )
    assert target["builder"] == "build_future_variance_targets"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid_json_object:{path}")
    return value


if __name__ == "__main__":
    main()
