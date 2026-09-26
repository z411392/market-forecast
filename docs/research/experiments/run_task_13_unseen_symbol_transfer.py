from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import polars as pl
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


Market = Literal["us", "taiwan"]

START_DATE = date(2022, 7, 18)
TRAIN_END_DATE = date(2025, 11, 25)
EVALUATION_START_DATE = date(2025, 12, 4)
RIDGE_ALPHA = 1.0
BOOTSTRAP_BLOCK_LENGTH = 20
BOOTSTRAP_REPLICATES = 5000
BOOTSTRAP_SEED = 20260926


@dataclass(frozen=True)
class _InputSpec:
    symbol: str
    market: Market
    path: Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce Task #13 unseen-symbol Ridge-HAR and Pine comparator pilot."
    )
    for symbol in ("googl", "nvda", "qqq", "tsm", "2330", "2317", "2454"):
        parser.add_argument(f"--{symbol}", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def _qlike(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    ratio = actual / predicted
    return ratio - np.log(ratio) - 1.0


def _load(spec: _InputSpec) -> pl.DataFrame:
    frame = pl.read_csv(spec.path)
    required = {
        "time",
        "P4_INTRABAR_COUNT_5M",
        "P4_RV_WHOLE_DAY_5M",
        "P4_FORECAST_HARQ_VAR5",
        "P4_FORECAST_HAR_LEVEL_VAR5",
        "P4_FORECAST_GARCH_VAR5",
        "P4_FORECAST_EWMA_VAR5",
        "P4_FORECAST_NAIVE_VAR5",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{spec.symbol}: missing columns {sorted(missing)}")

    frame = frame.with_columns(
        pl.from_epoch("time", time_unit="s").dt.date().alias("date"),
        pl.lit(spec.symbol).alias("symbol"),
        pl.lit(spec.market).alias("market"),
    ).filter(pl.col("date") >= pl.lit(START_DATE))

    if spec.market == "us":
        count_valid = pl.col("P4_INTRABAR_COUNT_5M").is_in([78, 42])
    else:
        count_valid = pl.col("P4_INTRABAR_COUNT_5M") == 53

    rv_valid = (
        count_valid
        & pl.col("P4_RV_WHOLE_DAY_5M").is_finite()
        & (pl.col("P4_RV_WHOLE_DAY_5M") > 0.0)
    )
    frame = frame.with_columns(
        pl.when(rv_valid)
        .then(pl.col("P4_RV_WHOLE_DAY_5M"))
        .otherwise(None)
        .alias("rv")
    )

    rv = pl.col("rv")
    rv5 = rv.rolling_mean(window_size=5, min_samples=5)
    rv22 = rv.rolling_mean(window_size=22, min_samples=22)
    y5 = (
        rv.shift(-1)
        + rv.shift(-2)
        + rv.shift(-3)
        + rv.shift(-4)
        + rv.shift(-5)
    ) / 5.0

    return frame.with_columns(
        rv5.alias("rv5"),
        rv22.alias("rv22"),
        y5.alias("y5"),
    ).with_columns(
        (pl.col("rv") / pl.col("rv22")).log().alias("xD"),
        (pl.col("rv5") / pl.col("rv22")).log().alias("xW"),
        (pl.col("y5") / pl.col("rv22")).log().alias("z"),
    )


def _eligible(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.drop_nulls(["rv22", "y5", "xD", "xW", "z"])


def _fit_global(
    frames: dict[str, pl.DataFrame],
    held_out: str,
) -> tuple[StandardScaler, Ridge]:
    train = pl.concat(
        [
            _eligible(frame).filter(pl.col("date") <= pl.lit(TRAIN_END_DATE))
            for symbol, frame in frames.items()
            if symbol != held_out
        ],
        how="vertical",
    )
    x = train.select(["xD", "xW"]).to_numpy()
    y = train["z"].to_numpy()
    scaler = StandardScaler().fit(x)
    model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(x), y)
    return scaler, model


def _evaluate_symbol(
    frames: dict[str, pl.DataFrame],
    symbol: str,
) -> pl.DataFrame:
    scaler, model = _fit_global(frames, symbol)
    test = (
        _eligible(frames[symbol])
        .filter(pl.col("date") >= pl.lit(EVALUATION_START_DATE))
        .drop_nulls(
            [
                "P4_FORECAST_HARQ_VAR5",
                "P4_FORECAST_HAR_LEVEL_VAR5",
                "P4_FORECAST_GARCH_VAR5",
                "P4_FORECAST_EWMA_VAR5",
                "P4_FORECAST_NAIVE_VAR5",
            ]
        )
    )

    x = test.select(["xD", "xW"]).to_numpy()
    rv22 = test["rv22"].to_numpy()
    actual = test["y5"].to_numpy()
    global_pred = rv22 * np.exp(model.predict(scaler.transform(x)))

    predictions = {
        "global": global_pred,
        "har": test["P4_FORECAST_HAR_LEVEL_VAR5"].to_numpy(),
        "garch": test["P4_FORECAST_GARCH_VAR5"].to_numpy(),
        "harq": test["P4_FORECAST_HARQ_VAR5"].to_numpy(),
        "ewma": test["P4_FORECAST_EWMA_VAR5"].to_numpy(),
        "naive": test["P4_FORECAST_NAIVE_VAR5"].to_numpy(),
    }
    columns = [
        pl.Series(f"{name}_qlike", _qlike(actual, predicted))
        for name, predicted in predictions.items()
    ]
    return test.select(["date", "symbol", "market"]).with_columns(columns)


def _moving_block_ci(values: np.ndarray) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    n = len(values)
    if n < BOOTSTRAP_BLOCK_LENGTH:
        raise ValueError("not enough observations for block bootstrap")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = np.arange(n - BOOTSTRAP_BLOCK_LENGTH + 1)
    blocks_needed = math.ceil(n / BOOTSTRAP_BLOCK_LENGTH)
    means = np.empty(BOOTSTRAP_REPLICATES)
    for index in range(BOOTSTRAP_REPLICATES):
        picked = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate(
            [values[start : start + BOOTSTRAP_BLOCK_LENGTH] for start in picked]
        )[:n]
        means[index] = sample.mean()
    lower, upper = np.quantile(means, [0.025, 0.975])
    return float(values.mean()), float(lower), float(upper)


def _date_mean(rows: pl.DataFrame, market: str | None = None) -> pl.DataFrame:
    filtered = rows if market is None else rows.filter(pl.col("market") == market)
    qlike_columns = [name for name in filtered.columns if name.endswith("_qlike")]
    return filtered.group_by("date").agg(
        [pl.col(name).mean().alias(name) for name in qlike_columns]
    ).sort("date")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = _parse_args()
    specs = [
        _InputSpec("GOOGL", "us", args.googl),
        _InputSpec("NVDA", "us", args.nvda),
        _InputSpec("QQQ", "us", args.qqq),
        _InputSpec("TSM", "us", args.tsm),
        _InputSpec("2330", "taiwan", args.__dict__["2330"]),
        _InputSpec("2317", "taiwan", args.__dict__["2317"]),
        _InputSpec("2454", "taiwan", args.__dict__["2454"]),
    ]
    frames = {spec.symbol: _load(spec) for spec in specs}
    evaluations = {symbol: _evaluate_symbol(frames, symbol) for symbol in frames}
    all_rows = pl.concat(list(evaluations.values()), how="vertical")

    model_names = ("global", "har", "garch", "harq", "ewma", "naive")
    per_symbol = []
    for symbol, evaluated in evaluations.items():
        per_symbol.append(
            {
                "symbol": symbol,
                "market": evaluated["market"][0],
                "n_eval": evaluated.height,
                **{
                    f"{name}_qlike": float(evaluated[f"{name}_qlike"].mean())
                    for name in model_names
                },
            }
        )

    comparisons = (
        ("har", "global"),
        ("garch", "global"),
        ("har", "garch"),
        ("harq", "har"),
        ("ewma", "har"),
    )
    bootstrap = []
    for scope, market in (("overall", None), ("us", "us"), ("taiwan", "taiwan")):
        date_rows = _date_mean(all_rows, market)
        for first, second in comparisons:
            delta = (
                date_rows[f"{first}_qlike"].to_numpy()
                - date_rows[f"{second}_qlike"].to_numpy()
            )
            mean, lower, upper = _moving_block_ci(delta)
            bootstrap.append(
                {
                    "scope": scope,
                    "comparison": f"{first}_minus_{second}",
                    "n_dates": len(delta),
                    "mean_delta": mean,
                    "ci_025": lower,
                    "ci_975": upper,
                }
            )

    print("Per-symbol mean QLIKE")
    for row in per_symbol:
        print(row)
    print("\nPaired 20-session moving-block bootstrap")
    for row in bootstrap:
        print(row)

    if args.output_dir is not None:
        _write_csv(args.output_dir / "per_symbol_qlike.csv", per_symbol)
        _write_csv(args.output_dir / "bootstrap_comparisons.csv", bootstrap)


if __name__ == "__main__":
    main()
