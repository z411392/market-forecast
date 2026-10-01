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

EXPECTED_SHA256 = {
    "GOOGL": "2c09055672391ba0724d0918ddc86f621254154be20ef457c28b7a62f6ff34ba",
    "NVDA": "99323dc9644f2a5955f1b6119b2d75c7c6dcce8c7b2938be81c610871c5dc54c",
    "QQQ": "18fd0c5050c348516f616da8abcc764707f4aa669b7ba022a12ce1362954243e",
    "TSM": "f66835e9328fbe261472a8a693efb898ee144b1d90cfb38c0732037cc58abec4",
    "2330": "e26c29335402363c4a1b8aae35bb26e63bb1577bed74173f5b914f7258ca3d47",
    "2317": "98a0b83bb2ced641603a6b248853a0fc288a80d06cae4f8212ab813d54866c5c",
    "2454": "791626c2890e5aad95d19abc4e4c84586686394b9f81b4fa2d53363465792847",
}


@dataclass(frozen=True)
class _InputSpec:
    symbol: str
    market: Market
    path: Path


@dataclass(frozen=True)
class _PanelData:
    dates: np.ndarray
    rv22: np.ndarray
    y5: np.ndarray
    x_d: np.ndarray
    x_w: np.ndarray
    z: np.ndarray


@dataclass(frozen=True)
class _Evaluation:
    dates: np.ndarray
    global_qlike: np.ndarray
    market_qlike: np.ndarray
    market_minus_global: np.ndarray


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


def _float_or_nan(row: dict[str, str], key: str) -> float:
    value = row[key].strip()
    return float(value) if value else math.nan


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full(values.size, np.nan)
    for index in range(window - 1, values.size):
        sample = values[index - window + 1 : index + 1]
        if np.all(np.isfinite(sample)):
            result[index] = float(sample.mean())
    return result


def _load(spec: _InputSpec) -> _PanelData:
    dates: list[date] = []
    counts: list[float] = []
    realized_variances: list[float] = []

    with spec.path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {
            "time",
            "P4_INTRABAR_COUNT_5M",
            "P4_RV_WHOLE_DAY_5M",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{spec.symbol}: missing columns {sorted(missing)}")

        for row in reader:
            session_date = datetime.fromtimestamp(
                int(float(row["time"])),
                tz=timezone.utc,
            ).date()
            if session_date < START_DATE:
                continue
            dates.append(session_date)
            counts.append(_float_or_nan(row, "P4_INTRABAR_COUNT_5M"))
            realized_variances.append(_float_or_nan(row, "P4_RV_WHOLE_DAY_5M"))

    date_array = np.array(dates, dtype=object)
    count_array = np.array(counts, dtype=float)
    rv = np.array(realized_variances, dtype=float)

    if spec.market == "us":
        valid_count = np.isin(count_array, np.array([78.0, 42.0]))
    else:
        valid_count = count_array == 53.0

    rv = np.where(valid_count & np.isfinite(rv) & (rv > 0.0), rv, np.nan)
    rv5 = _rolling_mean(rv, 5)
    rv22 = _rolling_mean(rv, 22)

    y5 = np.full(rv.size, np.nan)
    for index in range(rv.size - 5):
        future = rv[index + 1 : index + 6]
        if np.all(np.isfinite(future)):
            y5[index] = float(future.mean())

    with np.errstate(divide="ignore", invalid="ignore"):
        x_d = np.log(rv / rv22)
        x_w = np.log(rv5 / rv22)
        z = np.log(y5 / rv22)

    return _PanelData(
        dates=date_array,
        rv22=rv22,
        y5=y5,
        x_d=x_d,
        x_w=x_w,
        z=z,
    )


def _eligible_mask(data: _PanelData) -> np.ndarray:
    return (
        np.isfinite(data.rv22)
        & np.isfinite(data.y5)
        & np.isfinite(data.x_d)
        & np.isfinite(data.x_w)
        & np.isfinite(data.z)
    )


def _training_rows(
    data: dict[str, _PanelData],
    specs: dict[str, _InputSpec],
    held_out: str,
    market_only: bool,
) -> tuple[np.ndarray, np.ndarray]:
    held_market = specs[held_out].market
    x_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []

    for symbol, panel in data.items():
        if symbol == held_out:
            continue
        if market_only and specs[symbol].market != held_market:
            continue

        before_cutoff = np.array(
            [session_date <= TRAIN_END_DATE for session_date in panel.dates],
            dtype=bool,
        )
        mask = _eligible_mask(panel) & before_cutoff
        x_parts.append(np.column_stack((panel.x_d[mask], panel.x_w[mask])))
        y_parts.append(panel.z[mask])

    if not x_parts:
        raise ValueError(f"{held_out}: no training symbols remain")

    return np.vstack(x_parts), np.concatenate(y_parts)


def _predict(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    rv22: np.ndarray,
) -> np.ndarray:
    scaler = StandardScaler().fit(train_x)
    model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(train_x), train_y)
    normalized = model.predict(scaler.transform(test_x))
    return rv22 * np.exp(normalized)


def _qlike(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    ratio = actual / predicted
    return ratio - np.log(ratio) - 1.0


def _evaluate_symbol(
    data: dict[str, _PanelData],
    specs: dict[str, _InputSpec],
    held_out: str,
) -> _Evaluation:
    panel = data[held_out]
    after_start = np.array(
        [session_date >= EVALUATION_START_DATE for session_date in panel.dates],
        dtype=bool,
    )
    mask = _eligible_mask(panel) & after_start

    test_x = np.column_stack((panel.x_d[mask], panel.x_w[mask]))
    actual = panel.y5[mask]
    rv22 = panel.rv22[mask]

    global_x, global_y = _training_rows(
        data,
        specs,
        held_out,
        market_only=False,
    )
    market_x, market_y = _training_rows(
        data,
        specs,
        held_out,
        market_only=True,
    )

    global_pred = _predict(global_x, global_y, test_x, rv22)
    market_pred = _predict(market_x, market_y, test_x, rv22)
    global_loss = _qlike(actual, global_pred)
    market_loss = _qlike(actual, market_pred)

    return _Evaluation(
        dates=panel.dates[mask],
        global_qlike=global_loss,
        market_qlike=market_loss,
        market_minus_global=market_loss - global_loss,
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
        sample = np.concatenate([values[start : start + BOOTSTRAP_BLOCK_LENGTH] for start in chosen])[
            : values.size
        ]
        means[index] = sample.mean()

    lower, upper = np.quantile(means, [0.025, 0.975])
    return float(values.mean()), float(lower), float(upper)


def _scope_row(
    evaluations: dict[str, _Evaluation],
    specs: dict[str, _InputSpec],
    name: str,
    market: Market | None,
) -> dict[str, object]:
    per_date: dict[date, list[tuple[float, float, float]]] = {}

    for symbol, evaluated in evaluations.items():
        if market is not None and specs[symbol].market != market:
            continue
        for session_date, global_loss, market_loss, delta in zip(
            evaluated.dates,
            evaluated.global_qlike,
            evaluated.market_qlike,
            evaluated.market_minus_global,
            strict=True,
        ):
            per_date.setdefault(session_date, []).append(
                (float(global_loss), float(market_loss), float(delta))
            )

    global_by_date: list[float] = []
    market_by_date: list[float] = []
    delta_by_date: list[float] = []

    for session_date in sorted(per_date):
        values = per_date[session_date]
        global_by_date.append(float(np.mean([value[0] for value in values])))
        market_by_date.append(float(np.mean([value[1] for value in values])))
        delta_by_date.append(float(np.mean([value[2] for value in values])))

    delta_array = np.array(delta_by_date, dtype=float)
    mean_delta, lower, upper = _moving_block_ci(delta_array)
    return {
        "kind": "scope",
        "name": name,
        "market": market or "all",
        "n": len(delta_by_date),
        "global_qlike": float(np.mean(global_by_date)),
        "market_qlike": float(np.mean(market_by_date)),
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

    for spec in input_specs:
        actual_hash = _sha256(spec.path)
        expected_hash = EXPECTED_SHA256[spec.symbol]
        if actual_hash != expected_hash:
            raise ValueError(f"{spec.symbol}: input SHA-256 {actual_hash} " f"!= expected {expected_hash}")

    specs = {spec.symbol: spec for spec in input_specs}
    data = {spec.symbol: _load(spec) for spec in input_specs}
    evaluations = {symbol: _evaluate_symbol(data, specs, symbol) for symbol in data}

    summaries: list[dict[str, object]] = []
    for symbol, evaluated in evaluations.items():
        mean_delta, lower, upper = _moving_block_ci(evaluated.market_minus_global)
        summaries.append(
            {
                "kind": "symbol",
                "name": symbol,
                "market": specs[symbol].market,
                "n": evaluated.dates.size,
                "global_qlike": float(evaluated.global_qlike.mean()),
                "market_qlike": float(evaluated.market_qlike.mean()),
                "market_minus_global": mean_delta,
                "ci_025": lower,
                "ci_975": upper,
            }
        )

    summaries.extend(
        [
            _scope_row(evaluations, specs, "overall", None),
            _scope_row(evaluations, specs, "us", "us"),
            _scope_row(evaluations, specs, "taiwan", "taiwan"),
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
