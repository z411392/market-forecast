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
Mode = Literal["global", "market", "partial"]

START_DATE = date(2022, 7, 18)
EVALUATION_START_DATE = date(2025, 12, 4)
HORIZON = 20
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
    maturity_dates: np.ndarray
    rv22: np.ndarray
    y20: np.ndarray
    x_d: np.ndarray
    x_w: np.ndarray
    z: np.ndarray


@dataclass(frozen=True)
class _Evaluation:
    dates: np.ndarray
    global_qlike: np.ndarray
    market_qlike: np.ndarray
    partial_qlike: np.ndarray


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Task #29 H=20 confirmatory transfer experiment.")
    for symbol in ("googl", "nvda", "qqq", "tsm", "2330", "2317", "2454"):
        parser.add_argument(f"--{symbol}", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(row: dict[str, str], key: str) -> float:
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
            counts.append(_number(row, "P4_INTRABAR_COUNT_5M"))
            realized_variances.append(_number(row, "P4_RV_WHOLE_DAY_5M"))

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

    y20 = np.full(rv.size, np.nan)
    maturity_dates = np.empty(rv.size, dtype=object)
    maturity_dates[:] = None
    for index in range(rv.size - HORIZON):
        future = rv[index + 1 : index + HORIZON + 1]
        if np.all(np.isfinite(future)):
            y20[index] = float(future.mean())
            maturity_dates[index] = date_array[index + HORIZON]

    with np.errstate(divide="ignore", invalid="ignore"):
        x_d = np.log(rv / rv22)
        x_w = np.log(rv5 / rv22)
        z = np.log(y20 / rv22)

    return _PanelData(
        dates=date_array,
        maturity_dates=maturity_dates,
        rv22=rv22,
        y20=y20,
        x_d=x_d,
        x_w=x_w,
        z=z,
    )


def _eligible(data: _PanelData) -> np.ndarray:
    return (
        np.isfinite(data.rv22)
        & np.isfinite(data.y20)
        & np.isfinite(data.x_d)
        & np.isfinite(data.x_w)
        & np.isfinite(data.z)
    )


def _market_code(market: Market) -> float:
    return -0.5 if market == "us" else 0.5


def _design(
    x_d: np.ndarray,
    x_w: np.ndarray,
    market: Market,
    partial: bool,
) -> np.ndarray:
    if not partial:
        return np.column_stack((x_d, x_w))

    market_code = _market_code(market)
    market_column = np.full(x_d.size, market_code)
    return np.column_stack(
        (
            x_d,
            x_w,
            market_column,
            market_code * x_d,
            market_code * x_w,
        )
    )


def _training_rows(
    data: dict[str, _PanelData],
    specs: dict[str, _InputSpec],
    held_out: str,
    mode: Mode,
) -> tuple[np.ndarray, np.ndarray]:
    held_market = specs[held_out].market
    x_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []

    for symbol, panel in data.items():
        if symbol == held_out:
            continue
        if mode == "market" and specs[symbol].market != held_market:
            continue

        matured_before_evaluation = np.array(
            [
                maturity_date is not None and maturity_date < EVALUATION_START_DATE
                for maturity_date in panel.maturity_dates
            ],
            dtype=bool,
        )
        mask = _eligible(panel) & matured_before_evaluation
        x_parts.append(
            _design(
                panel.x_d[mask],
                panel.x_w[mask],
                specs[symbol].market,
                partial=mode == "partial",
            )
        )
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
    z_hat = model.predict(scaler.transform(test_x))
    return rv22 * np.exp(z_hat)


def _qlike(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    ratio = actual / predicted
    return ratio - np.log(ratio) - 1.0


def _evaluate(
    data: dict[str, _PanelData],
    specs: dict[str, _InputSpec],
    held_out: str,
) -> _Evaluation:
    panel = data[held_out]
    after_start = np.array(
        [session_date >= EVALUATION_START_DATE for session_date in panel.dates],
        dtype=bool,
    )
    mask = _eligible(panel) & after_start

    x_d = panel.x_d[mask]
    x_w = panel.x_w[mask]
    actual = panel.y20[mask]
    rv22 = panel.rv22[mask]

    global_x, global_y = _training_rows(data, specs, held_out, "global")
    market_x, market_y = _training_rows(data, specs, held_out, "market")
    partial_x, partial_y = _training_rows(data, specs, held_out, "partial")

    base_test = _design(x_d, x_w, specs[held_out].market, partial=False)
    partial_test = _design(x_d, x_w, specs[held_out].market, partial=True)

    global_loss = _qlike(
        actual,
        _predict(global_x, global_y, base_test, rv22),
    )
    market_loss = _qlike(
        actual,
        _predict(market_x, market_y, base_test, rv22),
    )
    partial_loss = _qlike(
        actual,
        _predict(partial_x, partial_y, partial_test, rv22),
    )

    return _Evaluation(
        dates=panel.dates[mask],
        global_qlike=global_loss,
        market_qlike=market_loss,
        partial_qlike=partial_loss,
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


def _result_row(
    kind: str,
    name: str,
    market: str,
    global_loss: np.ndarray,
    market_loss: np.ndarray,
    partial_loss: np.ndarray,
) -> dict[str, object]:
    market_global = market_loss - global_loss
    partial_global = partial_loss - global_loss
    partial_market = partial_loss - market_loss

    mg_mean, mg_low, mg_high = _moving_block_ci(market_global)
    pg_mean, pg_low, pg_high = _moving_block_ci(partial_global)
    pm_mean, pm_low, pm_high = _moving_block_ci(partial_market)

    return {
        "kind": kind,
        "name": name,
        "market": market,
        "n": partial_loss.size,
        "global_qlike": float(global_loss.mean()),
        "market_qlike": float(market_loss.mean()),
        "partial_qlike": float(partial_loss.mean()),
        "market_minus_global": mg_mean,
        "market_global_ci_025": mg_low,
        "market_global_ci_975": mg_high,
        "partial_minus_global": pg_mean,
        "partial_global_ci_025": pg_low,
        "partial_global_ci_975": pg_high,
        "partial_minus_market": pm_mean,
        "partial_market_ci_025": pm_low,
        "partial_market_ci_975": pm_high,
    }


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
        for session_date, global_loss, market_loss, partial_loss in zip(
            evaluated.dates,
            evaluated.global_qlike,
            evaluated.market_qlike,
            evaluated.partial_qlike,
            strict=True,
        ):
            per_date.setdefault(session_date, []).append(
                (
                    float(global_loss),
                    float(market_loss),
                    float(partial_loss),
                )
            )

    date_rows = np.array(
        [np.mean(per_date[session_date], axis=0) for session_date in sorted(per_date)],
        dtype=float,
    )
    return _result_row(
        "scope",
        name,
        market or "all",
        date_rows[:, 0],
        date_rows[:, 1],
        date_rows[:, 2],
    )


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
    evaluations = {symbol: _evaluate(data, specs, symbol) for symbol in data}

    rows: list[dict[str, object]] = []
    for symbol, evaluated in evaluations.items():
        rows.append(
            _result_row(
                "symbol",
                symbol,
                specs[symbol].market,
                evaluated.global_qlike,
                evaluated.market_qlike,
                evaluated.partial_qlike,
            )
        )

    rows.extend(
        [
            _scope_row(evaluations, specs, "overall", None),
            _scope_row(evaluations, specs, "us", "us"),
            _scope_row(evaluations, specs, "taiwan", "taiwan"),
        ]
    )

    print("Input SHA-256")
    for spec in input_specs:
        print(f"{spec.symbol}: {_sha256(spec.path)}")
    print("\nH=20 transfer results")
    for row in rows:
        print(row)

    if args.output is not None:
        _write_csv(args.output, rows)


if __name__ == "__main__":
    main()
