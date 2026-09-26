from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


VAR_TOLERANCE = 1e-15
DISPLAY_TOLERANCE = 1e-10


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Risk Forecast HAR Frozen v1 manifest against golden fixtures."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/model-manifests/risk_forecast_har_frozen_v1.json"),
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path("artifacts/model-manifests/risk_forecast_har_frozen_v1_golden.csv"),
    )
    return parser.parse_args()


def _assert_close(name: str, actual: float, expected: float, tolerance: float) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(
            f"{name}: actual={actual:.17g} expected={expected:.17g} "
            f"abs_diff={abs(actual - expected):.17g}"
        )


def main() -> None:
    args = _parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    with args.golden.open(newline="", encoding="utf-8") as handle:
        rows = tuple(csv.DictReader(handle))

    if manifest["manifest_version"] != "risk_forecast_har_frozen_v1":
        raise AssertionError("unexpected manifest version")

    symbols = manifest["symbols"]
    if len(rows) != len(symbols):
        raise AssertionError("golden fixture count does not match manifest")

    for row in rows:
        tickerid = row["tickerid"]
        entry = symbols[tickerid]
        coefficients = entry["coefficients"]

        rv1 = float(row["rv1"])
        rv5 = float(row["rv5"])
        rv22 = float(row["rv22"])

        forecast = (
            coefficients["intercept_variance"]
            + coefficients["beta_d"] * rv1
            + coefficients["beta_w"] * rv5
            + coefficients["beta_m"] * rv22
        )
        expected_forecast = float(row["forecast_var5"])
        _assert_close(
            f"{tickerid} forecast",
            forecast,
            expected_forecast,
            VAR_TOLERANCE,
        )

        annualized_vol = math.sqrt(forecast * 252.0) * 100.0
        expected_vol = float(row["annualized_vol_pct"])
        _assert_close(
            f"{tickerid} annualized vol",
            annualized_vol,
            expected_vol,
            DISPLAY_TOLERANCE,
        )

        move5 = math.sqrt(forecast * 5.0) * 100.0
        expected_move5 = float(row["move5_1sigma_pct"])
        _assert_close(
            f"{tickerid} 5D move",
            move5,
            expected_move5,
            DISPLAY_TOLERANCE,
        )

        _assert_close(
            f"{tickerid} manifest reconstruction",
            entry["python_reconstructed_forecast_variance"],
            expected_forecast,
            VAR_TOLERANCE,
        )
        _assert_close(
            f"{tickerid} freeze-bar export",
            entry["freeze_bar_export_forecast_variance"],
            expected_forecast,
            VAR_TOLERANCE,
        )

    print(
        f"PASS: {len(rows)} frozen HAR golden fixtures "
        f"(variance_tol={VAR_TOLERANCE:g}, display_tol={DISPLAY_TOLERANCE:g})"
    )


if __name__ == "__main__":
    main()
