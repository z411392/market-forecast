from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path


VAR_TOLERANCE = 1e-15
DISPLAY_TOLERANCE = 1e-10


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify HAR Frozen v1 manifest, golden fixtures, and Pine constants."
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
    parser.add_argument(
        "--pine",
        type=Path,
        default=Path("pine/risk_forecast_v1_5_tv_har_frozen_v1.pine"),
    )
    return parser.parse_args()


def _assert_close(name: str, actual: float, expected: float, tolerance: float) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(
            f"{name}: actual={actual:.17g} expected={expected:.17g} "
            f"abs_diff={abs(actual - expected):.17g}"
        )


def _read_pine_constants(path: Path) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    current: str | None = None
    ticker_pattern = re.compile(r'(?:if|else if) tickerId == "([^"]+)"')
    value_pattern = re.compile(
        r"(beta0|betaD|betaW|betaM|freezeYear|freezeMonth|freezeDay) := (.+)"
    )

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        ticker_match = ticker_pattern.fullmatch(line)
        if ticker_match:
            current = ticker_match.group(1)
            result[current] = {}
            continue

        if current is None:
            continue

        value_match = value_pattern.fullmatch(line)
        if value_match:
            name, raw_value = value_match.groups()
            if name.startswith("freeze"):
                result[current][name] = int(raw_value)
            else:
                result[current][name] = float(raw_value)

    required = {
        "beta0",
        "betaD",
        "betaW",
        "betaM",
        "freezeYear",
        "freezeMonth",
        "freezeDay",
    }
    for tickerid, values in result.items():
        missing = required.difference(values)
        if missing:
            raise AssertionError(f"{tickerid}: Pine constants missing {sorted(missing)}")

    return result


def main() -> None:
    args = _parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    with args.golden.open(newline="", encoding="utf-8") as handle:
        rows = tuple(csv.DictReader(handle))

    if manifest["manifest_version"] != "risk_forecast_har_frozen_v1":
        raise AssertionError("unexpected manifest version")

    symbols = manifest["symbols"]
    pine_constants = _read_pine_constants(args.pine)

    if len(rows) != len(symbols):
        raise AssertionError("golden fixture count does not match manifest")
    if set(pine_constants) != set(symbols):
        raise AssertionError("Pine ticker set does not match manifest ticker set")

    for row in rows:
        tickerid = row["tickerid"]
        entry = symbols[tickerid]
        coefficients = entry["coefficients"]
        pine = pine_constants[tickerid]

        _assert_close(
            f"{tickerid} Pine beta0",
            float(pine["beta0"]),
            coefficients["intercept_variance"],
            VAR_TOLERANCE,
        )
        _assert_close(
            f"{tickerid} Pine betaD",
            float(pine["betaD"]),
            coefficients["beta_d"],
            VAR_TOLERANCE,
        )
        _assert_close(
            f"{tickerid} Pine betaW",
            float(pine["betaW"]),
            coefficients["beta_w"],
            VAR_TOLERANCE,
        )
        _assert_close(
            f"{tickerid} Pine betaM",
            float(pine["betaM"]),
            coefficients["beta_m"],
            VAR_TOLERANCE,
        )

        freeze_date = (
            f"{int(pine['freezeYear']):04d}-"
            f"{int(pine['freezeMonth']):02d}-"
            f"{int(pine['freezeDay']):02d}"
        )
        if freeze_date != entry["fit_bar_date"]:
            raise AssertionError(
                f"{tickerid}: Pine freeze date {freeze_date} "
                f"!= manifest {entry['fit_bar_date']}"
            )

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

    pine_text = args.pine.read_text(encoding="utf-8")
    if "ticker.standard(syminfo.tickerid)" not in pine_text:
        raise AssertionError("Pine does not canonicalize modified ticker IDs")
    for forbidden in ("matrix.", "pinv", "TRAIN_WINDOW", "garchVarianceForecast"):
        if forbidden in pine_text:
            raise AssertionError(f"forbidden inference-only token present: {forbidden}")

    print(
        f"PASS: {len(rows)} manifest/golden/Pine fixtures "
        f"(variance_tol={VAR_TOLERANCE:g}, display_tol={DISPLAY_TOLERANCE:g})"
    )


if __name__ == "__main__":
    main()
