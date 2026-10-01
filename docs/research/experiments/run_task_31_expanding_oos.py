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
HORIZON = 5
RIDGE_ALPHA = 1.0
BOOTSTRAP_BLOCK_LENGTH = 20
BOOTSTRAP_REPLICATES = 5000
BOOTSTRAP_SEED = 20260926

FOLDS = (
    ("F1", date(2024, 12, 2), date(2025, 3, 31)),
    ("F2", date(2025, 4, 1), date(2025, 7, 31)),
    ("F3", date(2025, 8, 1), date(2025, 12, 3)),
    ("F4", date(2025, 12, 4), None),
)

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
    y5: np.ndarray
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
    parser = argparse.ArgumentParser(
        description="Run Task #31 multiple-window expanding-OOS transfer stability test."
    )
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

    y5 = np.full(rv.size, np.nan)
    maturity_dates = np.empty(rv.size, dtype=object)
    maturity_dates[:] = None
    for index in range(rv.size - HORIZON):
        future = rv[index + 1 : index + HORIZON + 1]
        if np.all(np.isfinite(future)):
            y5[index] = float(future.mean())
            maturity_dates[index] = date_array[index + HORIZON]

    with np.errstate(divide="ignore", invalid="ignore"):
        x_d = np.log(rv / rv22)
        x_w = np.log(rv5 / rv22)
        z = np.log(y5 / rv22)

    return _PanelData(
        dates=date_array,
        maturity_dates=maturity_dates,
        rv22=rv22,
        y5=y5,
        x_d=x_d,
        x_w=x_w,
        z=z,
    )


def _eligible(data: _PanelData) -> np.ndarray:
    return (
        np.isfinite(data.rv22)
        & np.isfinite(data.y5)
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

    code = _market_code(market)
    market_column = np.full(x_d.size, code)
    return np.column_stack(
        (
            x_d,
            x_w,
            market_column,
            code * x_d,
            code * x_w,
        )
    )


def _training_rows(
    data: dict[str, _PanelData],
    specs: dict[str, _InputSpec],
    held_out: str,
    mode: Mode,
    fold_start: date,
) -> tuple[np.ndarray, np.ndarray]:
    held_market = specs[held_out].market
    x_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []

    for symbol, panel in data.items():
        if symbol == held_out:
            continue
        if mode == "market" and specs[symbol].market != held_market:
            continue

        matured_before_fold = np.array(
            [
                maturity_date is not None and maturity_date < fold_start
                for maturity_date in panel.maturity_dates
            ],
            dtype=bool,
        )
        mask = _eligible(panel) & matured_before_fold
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
        raise ValueError(f"{held_out}: no training symbols remain for fold {fold_start}")

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


def _evaluate_symbol(
    data: dict[str, _PanelData],
    specs: dict[str, _InputSpec],
    held_out: str,
    fold_start: date,
    fold_end: date | None,
) -> _Evaluation:
    panel = data[held_out]
    in_window = np.array(
        [
            session_date >= fold_start and (fold_end is None or session_date <= fold_end)
            for session_date in panel.dates
        ],
        dtype=bool,
    )
    mask = _eligible(panel) & in_window

    x_d = panel.x_d[mask]
    x_w = panel.x_w[mask]
    actual = panel.y5[mask]
    rv22 = panel.rv22[mask]

    base_test = _design(x_d, x_w, specs[held_out].market, partial=False)
    partial_test = _design(x_d, x_w, specs[held_out].market, partial=True)

    losses: dict[Mode, np.ndarray] = {}
    for mode, test_x in (
        ("global", base_test),
        ("market", base_test),
        ("partial", partial_test),
    ):
        train_x, train_y = _training_rows(
            data,
            specs,
            held_out,
            mode,
            fold_start,
        )
        losses[mode] = _qlike(
            actual,
            _predict(train_x, train_y, test_x, rv22),
        )

    return _Evaluation(
        dates=panel.dates[mask],
        global_qlike=losses["global"],
        market_qlike=losses["market"],
        partial_qlike=losses["partial"],
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
    fold_id: str,
    fold_start: date,
    fold_end: date | None,
    evaluations: dict[str, _Evaluation],
    specs: dict[str, _InputSpec],
    scope: str,
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
    market_global = date_rows[:, 1] - date_rows[:, 0]
    partial_global = date_rows[:, 2] - date_rows[:, 0]
    partial_market = date_rows[:, 2] - date_rows[:, 1]

    mg_mean, mg_low, mg_high = _moving_block_ci(market_global)
    pg_mean, pg_low, pg_high = _moving_block_ci(partial_global)
    pm_mean, pm_low, pm_high = _moving_block_ci(partial_market)

    return {
        "fold": fold_id,
        "start": fold_start.isoformat(),
        "end": fold_end.isoformat() if fold_end is not None else "end",
        "scope": scope,
        "n_dates": date_rows.shape[0],
        "global_qlike": float(date_rows[:, 0].mean()),
        "market_qlike": float(date_rows[:, 1].mean()),
        "partial_qlike": float(date_rows[:, 2].mean()),
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
            raise ValueError(f"{spec.symbol}: input SHA-256 {actual_hash} != expected {expected_hash}")

    specs = {spec.symbol: spec for spec in input_specs}
    data = {spec.symbol: _load(spec) for spec in input_specs}
    rows: list[dict[str, object]] = []

    for fold_id, fold_start, fold_end in FOLDS:
        evaluations = {
            symbol: _evaluate_symbol(
                data,
                specs,
                symbol,
                fold_start,
                fold_end,
            )
            for symbol in data
        }
        rows.extend(
            [
                _scope_row(
                    fold_id,
                    fold_start,
                    fold_end,
                    evaluations,
                    specs,
                    "overall",
                    None,
                ),
                _scope_row(
                    fold_id,
                    fold_start,
                    fold_end,
                    evaluations,
                    specs,
                    "us",
                    "us",
                ),
                _scope_row(
                    fold_id,
                    fold_start,
                    fold_end,
                    evaluations,
                    specs,
                    "taiwan",
                    "taiwan",
                ),
            ]
        )

    print("Input SHA-256")
    for spec in input_specs:
        print(f"{spec.symbol}: {_sha256(spec.path)}")
    print("\nExpanding-OOS transfer stability")
    for row in rows:
        print(row)

    if args.output is not None:
        _write_csv(args.output, rows)


if __name__ == "__main__":
    main()
