from __future__ import annotations

import argparse
import csv
import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np

Market = Literal["us", "taiwan"]

HORIZON = 5
HAR_WEEK = 5
HAR_MONTH = 22
TRAIN_WINDOW = 504
EVALUATION_START = date(2025, 12, 4)
BOOTSTRAP_BLOCK = 20
BOOTSTRAP_REPLICATES = 5000
BOOTSTRAP_SEED = 20260926
EPS = 1e-12


@dataclass(frozen=True)
class InputSpec:
    symbol: str
    market: Market
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Matched Level-HAR vs Log-HAR Task #23 experiment.")
    for symbol in ("googl", "nvda", "qqq", "tsm", "2330", "2317", "2454"):
        parser.add_argument(f"--{symbol}", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def read_export(spec: InputSpec) -> dict[str, np.ndarray]:
    with spec.path.open(newline="", encoding="utf-8-sig") as handle:
        rows = tuple(csv.DictReader(handle))

    required = {
        "time",
        "P4_INTRABAR_COUNT_5M",
        "P4_RV_WHOLE_DAY_5M",
        "P4_FORECAST_HAR_LEVEL_VAR5",
    }
    missing = required.difference(rows[0])
    if missing:
        raise ValueError(f"{spec.symbol}: missing columns {sorted(missing)}")

    def number(row: dict[str, str], key: str) -> float:
        value = row[key].strip()
        return float(value) if value else math.nan

    times = np.array([int(float(row["time"])) for row in rows], dtype=np.int64)
    dates = np.array([datetime.fromtimestamp(value, timezone.utc).date() for value in times], dtype=object)
    counts = np.array([number(row, "P4_INTRABAR_COUNT_5M") for row in rows], dtype=float)
    rv = np.array([number(row, "P4_RV_WHOLE_DAY_5M") for row in rows], dtype=float)
    exported_level = np.array([number(row, "P4_FORECAST_HAR_LEVEL_VAR5") for row in rows], dtype=float)
    return {
        "date": dates,
        "count": counts,
        "rv": rv,
        "exported_level": exported_level,
    }


def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full(values.size, np.nan)
    for index in range(window - 1, values.size):
        segment = values[index - window + 1 : index + 1]
        if np.all(np.isfinite(segment)):
            result[index] = float(np.mean(segment))
    return result


def fit_har_path(rv: np.ndarray, use_log: bool) -> np.ndarray:
    rv5 = rolling_mean(rv, HAR_WEEK)
    rv22 = rolling_mean(rv, HAR_MONTH)
    matured = rolling_mean(rv, HORIZON)

    if use_log:
        d = np.log(rv)
        w = np.log(rv5)
        m = np.log(rv22)
        target = np.log(matured)
    else:
        d = rv.copy()
        w = rv5.copy()
        m = rv22.copy()
        target = matured.copy()

    train_d = np.roll(d, HORIZON)
    train_w = np.roll(w, HORIZON)
    train_m = np.roll(m, HORIZON)
    train_d[:HORIZON] = np.nan
    train_w[:HORIZON] = np.nan
    train_m[:HORIZON] = np.nan

    forecast = np.full(rv.size, np.nan)
    for index in range(TRAIN_WINDOW - 1, rv.size):
        left = index - TRAIN_WINDOW + 1
        td = train_d[left : index + 1]
        tw = train_w[left : index + 1]
        tm = train_m[left : index + 1]
        ty = target[left : index + 1]
        current = np.array([d[index], w[index], m[index]], dtype=float)
        if not (
            np.all(np.isfinite(td))
            and np.all(np.isfinite(tw))
            and np.all(np.isfinite(tm))
            and np.all(np.isfinite(ty))
            and np.all(np.isfinite(current))
        ):
            continue

        means = np.array([td.mean(), tw.mean(), tm.mean()], dtype=float)
        mean_y = float(ty.mean())
        centered = np.column_stack((td, tw, tm)) - means
        centered_y = ty - mean_y
        covariance = centered.T @ centered / TRAIN_WINDOW
        covariance_y = centered.T @ centered_y / TRAIN_WINDOW
        beta = np.linalg.pinv(covariance) @ covariance_y
        intercept = mean_y - float(beta @ means)
        prediction = intercept + float(beta @ current)
        if use_log:
            prediction = math.exp(prediction)
        forecast[index] = max(prediction, EPS)

    return forecast


def clean_scoring_target(spec: InputSpec, data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    rv = data["rv"]
    count = data["count"]
    if spec.market == "us":
        valid_count = np.isin(count, np.array([78.0, 42.0]))
    else:
        valid_count = count == 53.0

    clean_rv = np.where(valid_count & np.isfinite(rv) & (rv > 0.0), rv, np.nan)
    trailing22 = rolling_mean(clean_rv, HAR_MONTH)
    target = np.full(rv.size, np.nan)
    for index in range(rv.size - HORIZON):
        future = clean_rv[index + 1 : index + HORIZON + 1]
        if np.all(np.isfinite(future)):
            target[index] = float(np.mean(future))
    return trailing22, target


def qlike(actual: np.ndarray, forecast: np.ndarray) -> np.ndarray:
    ratio = actual / forecast
    return ratio - np.log(ratio) - 1.0


def moving_block_ci(values: np.ndarray) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    if values.size < BOOTSTRAP_BLOCK:
        raise ValueError("not enough observations for block bootstrap")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = np.arange(values.size - BOOTSTRAP_BLOCK + 1)
    blocks_needed = math.ceil(values.size / BOOTSTRAP_BLOCK)
    means = np.empty(BOOTSTRAP_REPLICATES)
    for iteration in range(BOOTSTRAP_REPLICATES):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate([values[start : start + BOOTSTRAP_BLOCK] for start in chosen])[: values.size]
        means[iteration] = sample.mean()
    lower, upper = np.quantile(means, [0.025, 0.975])
    return float(values.mean()), float(lower), float(upper)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    args = parse_args()
    specs = (
        InputSpec("GOOGL", "us", args.googl),
        InputSpec("NVDA", "us", args.nvda),
        InputSpec("QQQ", "us", args.qqq),
        InputSpec("TSM", "us", args.tsm),
        InputSpec("2330", "taiwan", getattr(args, "2330")),
        InputSpec("2317", "taiwan", getattr(args, "2317")),
        InputSpec("2454", "taiwan", getattr(args, "2454")),
    )

    scored: list[dict[str, object]] = []
    per_symbol: list[dict[str, object]] = []
    parity: list[dict[str, object]] = []

    for spec in specs:
        data = read_export(spec)
        level = fit_har_path(data["rv"], use_log=False)
        log_har = fit_har_path(data["rv"], use_log=True)

        parity_mask = np.isfinite(level) & np.isfinite(data["exported_level"])
        parity_error = np.abs(level[parity_mask] - data["exported_level"][parity_mask])
        parity.append(
            {
                "symbol": spec.symbol,
                "n_parity": int(parity_mask.sum()),
                "max_abs_level_export_diff": float(parity_error.max()),
                "input_sha256": file_sha256(spec.path),
            }
        )

        trailing22, actual = clean_scoring_target(spec, data)
        eligible = (
            np.array([value >= EVALUATION_START for value in data["date"]], dtype=bool)
            & np.isfinite(trailing22)
            & np.isfinite(actual)
            & np.isfinite(level)
            & np.isfinite(log_har)
        )
        level_loss = qlike(actual[eligible], level[eligible])
        log_loss = qlike(actual[eligible], log_har[eligible])
        delta = log_loss - level_loss

        mean_delta, lower, upper = moving_block_ci(delta)
        per_symbol.append(
            {
                "kind": "symbol",
                "name": spec.symbol,
                "market": spec.market,
                "n": int(eligible.sum()),
                "level_qlike": float(level_loss.mean()),
                "log_qlike": float(log_loss.mean()),
                "log_minus_level": mean_delta,
                "ci_025": lower,
                "ci_975": upper,
            }
        )

        eligible_indices = np.flatnonzero(eligible)
        for offset, index in enumerate(eligible_indices):
            scored.append(
                {
                    "date": data["date"][index],
                    "symbol": spec.symbol,
                    "market": spec.market,
                    "level_qlike": float(level_loss[offset]),
                    "log_qlike": float(log_loss[offset]),
                    "delta": float(delta[offset]),
                }
            )

    scopes: list[dict[str, object]] = []
    for scope_name, market in (("overall", None), ("us", "us"), ("taiwan", "taiwan")):
        relevant = [row for row in scored if market is None or row["market"] == market]
        dates = sorted({row["date"] for row in relevant})
        date_level = []
        for current_date in dates:
            rows = [row for row in relevant if row["date"] == current_date]
            date_level.append(
                {
                    "level": float(np.mean([row["level_qlike"] for row in rows])),
                    "log": float(np.mean([row["log_qlike"] for row in rows])),
                    "delta": float(np.mean([row["delta"] for row in rows])),
                }
            )
        deltas = np.array([row["delta"] for row in date_level], dtype=float)
        mean_delta, lower, upper = moving_block_ci(deltas)
        scopes.append(
            {
                "kind": "scope",
                "name": scope_name,
                "market": market or "all",
                "n": len(date_level),
                "level_qlike": float(np.mean([row["level"] for row in date_level])),
                "log_qlike": float(np.mean([row["log"] for row in date_level])),
                "log_minus_level": mean_delta,
                "ci_025": lower,
                "ci_975": upper,
            }
        )

    print("Level reconstruction parity")
    for row in parity:
        print(row)
    print("\nPer-symbol QLIKE")
    for row in per_symbol:
        print(row)
    print("\nDate-level equal-weight summaries")
    for row in scopes:
        print(row)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "kind",
            "name",
            "market",
            "n",
            "level_qlike",
            "log_qlike",
            "log_minus_level",
            "ci_025",
            "ci_975",
        ]
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(per_symbol + scopes)


if __name__ == "__main__":
    main()
