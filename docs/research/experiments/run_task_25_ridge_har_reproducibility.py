from __future__ import annotations

import argparse
import csv
import hashlib
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
        description="Reproduce Task #13 global vs market-specific Ridge-HAR pilot."
    )
    for symbol in ("googl", "nvda", "qqq", "tsm", "2330", "2317", "2454"):
        parser.add_argument(f"--{symbol}", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _qlike(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    ratio = actual / predicted
    return ratio - np.log(ratio) - 1.0


def _load(spec: _InputSpec) -> pl.DataFrame:
    frame = pl.read_csv(spec.path)
    required = {
        "time",
        "P4_INTRABAR_COUNT_5M",
        "P4_RV_WHOLE_DAY_5M",
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


def _fit(train: pl.DataFrame) -> tuple[StandardScaler, Ridge]:
    x = train.select(["xD", "xW"]).to_numpy()
    y = train["z"].to_numpy()
    scaler = StandardScaler().fit(x)
    model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(x), y)
    return scaler, model


def _training_rows(
    frames: dict[str, pl.DataFrame],
    specs: dict[str, _InputSpec],
    held_out: str,
    market_only: bool,
) -> pl.DataFrame:
    held_market = specs[held_out].market
    candidates = []
    for symbol, frame in frames.items():
        if symbol == held_out:
            continue
        if market_only and specs[symbol].market != held_market:
            continue
        candidates.append(
            _eligible(frame).filter(pl.col("date") <= pl.lit(TRAIN_END_DATE))
        )
    if not candidates:
        raise ValueError(f"{held_out}: no training symbols remain")
    return pl.concat(candidates, how="vertical")


def _predict(
    train: pl.DataFrame,
    test: pl.DataFrame,
) -> np.ndarray:
    scaler, model = _fit(train)
    x = test.select(["xD", "xW"]).to_numpy()
    normalized = model.predict(scaler.transform(x))
    return test["rv22"].to_numpy() * np.exp(normalized)


def _evaluate_symbol(
    frames: dict[str, pl.DataFrame],
    specs: dict[str, _InputSpec],
    held_out: str,
) -> pl.DataFrame:
    test = _eligible(frames[held_out]).filter(
        pl.col("date") >= pl.lit(EVALUATION_START_DATE)
    )
    global_train = _training_rows(frames, specs, held_out, market_only=False)
    market_train = _training_rows(frames, specs, held_out, market_only=True)

    actual = test["y5"].to_numpy()
    global_pred = _predict(global_train, test)
    market_pred = _predict(market_train, test)

    global_loss = _qlike(actual, global_pred)
    market_loss = _qlike(actual, market_pred)

    return test.select(["date", "symbol", "market"]).with_columns(
        pl.Series("global_qlike", global_loss),
        pl.Series("market_qlike", market_loss),
        pl.Series("market_minus_global", market_loss - global_loss),
    )


def _moving_block_ci(values: np.ndarray) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    if values.size < BOOTSTRAP_BLOCK_LENGTH:
        raise ValueError("not enough observations for block bootstrap")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = np.arange(values.size - BOOTSTRAP_BLOCK_LENGTH + 1)
    blocks_needed = math.ceil(values.size / BOOTSTRAP_BLOCK_LENGTH)
    means = np.empty(BOOTSTRAP_REPLICATES)

    for index in range(BOOTSTRAP_REPLICATES):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate(
            [
                values[start : start + BOOTSTRAP_BLOCK_LENGTH]
                for start in chosen
            ]
        )[: values.size]
        means[index] = sample.mean()

    lower, upper = np.quantile(means, [0.025, 0.975])
    return float(values.mean()), float(lower), float(upper)


def _summarize_scope(
    rows: pl.DataFrame,
    name: str,
    market: Market | None,
) -> dict[str, object]:
    filtered = rows if market is None else rows.filter(pl.col("market") == market)
    by_date = (
        filtered.group_by("date")
        .agg(
            pl.col("global_qlike").mean(),
            pl.col("market_qlike").mean(),
            pl.col("market_minus_global").mean(),
        )
        .sort("date")
    )
    mean_delta, lower, upper = _moving_block_ci(
        by_date["market_minus_global"].to_numpy()
    )
    return {
        "kind": "scope",
        "name": name,
        "market": market or "all",
        "n": by_date.height,
        "global_qlike": float(by_date["global_qlike"].mean()),
        "market_qlike": float(by_date["market_qlike"].mean()),
        "market_minus_global": mean_delta,
        "ci_025": lower,
        "ci_975": upper,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = _parse_args()
    input_specs = (
        _InputSpec("GOOGL", "us", args.googl),
        _InputSpec("NVDA", "us", args.nvda),
        _InputSpec("QQQ", "us", args.qqq),
        _InputSpec("TSM", "us", args.tsm),
        _InputSpec("2330", "taiwan", getattr(args, "2330")),
        _InputSpec("2317", "taiwan", getattr(args, "2317")),
        _InputSpec("2454", "taiwan", getattr(args, "2454")),
    )
    specs = {spec.symbol: spec for spec in input_specs}
    frames = {spec.symbol: _load(spec) for spec in input_specs}
    evaluations = {
        symbol: _evaluate_symbol(frames, specs, symbol)
        for symbol in frames
    }
    all_rows = pl.concat(list(evaluations.values()), how="vertical")

    summaries: list[dict[str, object]] = []
    for symbol, evaluated in evaluations.items():
        mean_delta, lower, upper = _moving_block_ci(
            evaluated["market_minus_global"].to_numpy()
        )
        summaries.append(
            {
                "kind": "symbol",
                "name": symbol,
                "market": specs[symbol].market,
                "n": evaluated.height,
                "global_qlike": float(evaluated["global_qlike"].mean()),
                "market_qlike": float(evaluated["market_qlike"].mean()),
                "market_minus_global": mean_delta,
                "ci_025": lower,
                "ci_975": upper,
            }
        )

    summaries.extend(
        [
            _summarize_scope(all_rows, "overall", None),
            _summarize_scope(all_rows, "us", "us"),
            _summarize_scope(all_rows, "taiwan", "taiwan"),
        ]
    )

    print("Input SHA-256")
    for spec in input_specs:
        print(f"{spec.symbol}: {_sha256(spec.path)}")
    print("\nGlobal vs market-specific Ridge-HAR")
    for row in summaries:
        print(row)

    if args.output is not None:
        _write_csv(args.output, summaries)


if __name__ == "__main__":
    main()
