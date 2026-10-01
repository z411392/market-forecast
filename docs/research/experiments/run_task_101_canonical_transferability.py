from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

Market = Literal["us", "taiwan"]
Mode = Literal["global", "market", "partial"]

PANEL_PATH = Path(
    "artifacts/private/provider-captures/task-101-canonical-panel/" "canonical-daily-panel.json"
)
OUTPUT_ROOT = Path("artifacts/private/provider-captures/task-101-transferability")
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
FINAL_H5_PATH = OUTPUT_ROOT / "h5-final.csv"
FOLDS_H5_PATH = OUTPUT_ROOT / "h5-expanding-oos.csv"
H20_PATH = OUTPUT_ROOT / "h20-confirmatory.csv"

START_DATE = date(2022, 7, 18)
TRAIN_END_DATE = date(2025, 11, 25)
EVALUATION_START_DATE = date(2025, 12, 4)
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


@dataclass(frozen=True)
class PanelData:
    dates: np.ndarray
    rv: np.ndarray
    rv22: np.ndarray
    target: np.ndarray
    maturity_dates: np.ndarray
    x_d: np.ndarray
    x_w: np.ndarray
    z: np.ndarray


@dataclass(frozen=True)
class Evaluation:
    dates: np.ndarray
    global_qlike: np.ndarray
    market_qlike: np.ndarray
    partial_qlike: np.ndarray


def main() -> None:
    panel = _load_panel(PANEL_PATH)
    markets = {symbol: _market(entry["market"]) for symbol, entry in panel["daily_values"].items()}
    data_h5 = {symbol: _build_panel(entry, 5) for symbol, entry in panel["daily_values"].items()}
    data_h20 = {symbol: _build_panel(entry, 20) for symbol, entry in panel["daily_values"].items()}

    final_h5 = _run_final_holdout(
        data=data_h5,
        markets=markets,
        horizon=5,
    )
    folds_h5 = _run_expanding_folds(
        data=data_h5,
        markets=markets,
    )
    final_h20 = _run_final_holdout(
        data=data_h20,
        markets=markets,
        horizon=20,
    )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    _write_csv(FINAL_H5_PATH, final_h5)
    _write_csv(FOLDS_H5_PATH, folds_h5)
    _write_csv(H20_PATH, final_h20)

    summary = {
        "task": 101,
        "slice": "S2-S3-transferability",
        "status": "accepted",
        "panel_sha256": _sha256(PANEL_PATH),
        "measurement_manifest_version": panel["measurement_manifest_version"],
        "ridge_alpha": RIDGE_ALPHA,
        "bootstrap": {
            "block_length": BOOTSTRAP_BLOCK_LENGTH,
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": BOOTSTRAP_SEED,
        },
        "final_h5": final_h5,
        "h5_expanding_oos": folds_h5,
        "final_h20": final_h20,
    }
    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_panel(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("task101_transfer_panel_not_object")
    if (
        value.get("artifact_version") != "task-101-canonical-daily-panel-v1"
        or value.get("measurement_frozen") is not True
    ):
        raise RuntimeError("task101_transfer_invalid_panel_identity")
    daily = value.get("daily_values")
    if not isinstance(daily, dict) or set(daily) != {
        "GOOGL",
        "NVDA",
        "QQQ",
        "TSM",
        "2330",
        "2317",
        "2454",
    }:
        raise RuntimeError("task101_transfer_unexpected_universe")
    return value


def _market(value: object) -> Market:
    if value == "us":
        return "us"
    if value == "taiwan":
        return "taiwan"
    raise RuntimeError("task101_transfer_invalid_market")


def _build_panel(
    entry: object,
    horizon: int,
) -> PanelData:
    if not isinstance(entry, dict):
        raise RuntimeError("task101_transfer_invalid_symbol_entry")
    rows = entry.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("task101_transfer_missing_rows")

    dates: list[date] = []
    rv_values: list[float] = []
    previous_date: date | None = None
    for raw in rows:
        if not isinstance(raw, dict):
            raise RuntimeError("task101_transfer_invalid_row")
        session_date = date.fromisoformat(_require_str(raw.get("session_date")))
        if session_date < START_DATE:
            raise RuntimeError("task101_transfer_row_before_start")
        if previous_date is not None and session_date <= previous_date:
            raise RuntimeError("task101_transfer_non_increasing_dates")
        previous_date = session_date
        dates.append(session_date)

        variance = raw.get("whole_day_variance")
        if variance is None:
            rv_values.append(math.nan)
        elif (
            isinstance(variance, bool)
            or not isinstance(variance, (int, float))
            or not math.isfinite(float(variance))
            or float(variance) <= 0.0
        ):
            raise RuntimeError("task101_transfer_invalid_variance")
        else:
            rv_values.append(float(variance))

    date_array = np.array(dates, dtype=object)
    rv = np.array(rv_values, dtype=float)
    rv5 = _rolling_mean(rv, 5)
    rv22 = _rolling_mean(rv, 22)

    target = np.full(rv.size, np.nan)
    maturity_dates = np.empty(rv.size, dtype=object)
    maturity_dates[:] = None
    for index in range(rv.size - horizon):
        future = rv[index + 1 : index + horizon + 1]
        if np.all(np.isfinite(future)):
            target[index] = float(future.mean())
            maturity_dates[index] = date_array[index + horizon]

    with np.errstate(divide="ignore", invalid="ignore"):
        x_d = np.log(rv / rv22)
        x_w = np.log(rv5 / rv22)
        z = np.log(target / rv22)

    return PanelData(
        dates=date_array,
        rv=rv,
        rv22=rv22,
        target=target,
        maturity_dates=maturity_dates,
        x_d=x_d,
        x_w=x_w,
        z=z,
    )


def _rolling_mean(
    values: np.ndarray,
    window: int,
) -> np.ndarray:
    result = np.full(values.size, np.nan)
    for index in range(window - 1, values.size):
        sample = values[index - window + 1 : index + 1]
        if np.all(np.isfinite(sample)):
            result[index] = float(sample.mean())
    return result


def _eligible(panel: PanelData) -> np.ndarray:
    return (
        np.isfinite(panel.rv22)
        & np.isfinite(panel.target)
        & np.isfinite(panel.x_d)
        & np.isfinite(panel.x_w)
        & np.isfinite(panel.z)
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
    *,
    data: dict[str, PanelData],
    markets: dict[str, Market],
    held_out: str,
    mode: Mode,
    maturity_before: date,
    origin_end: date | None,
) -> tuple[np.ndarray, np.ndarray]:
    held_market = markets[held_out]
    x_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []

    for symbol, panel in data.items():
        if symbol == held_out:
            continue
        if mode == "market" and markets[symbol] != held_market:
            continue

        matured = np.array(
            [value is not None and value < maturity_before for value in panel.maturity_dates],
            dtype=bool,
        )
        mask = _eligible(panel) & matured
        if origin_end is not None:
            mask &= np.array(
                [value <= origin_end for value in panel.dates],
                dtype=bool,
            )
        x_parts.append(
            _design(
                panel.x_d[mask],
                panel.x_w[mask],
                markets[symbol],
                partial=mode == "partial",
            )
        )
        y_parts.append(panel.z[mask])

    if not x_parts or any(part.size == 0 for part in y_parts):
        raise RuntimeError(f"task101_transfer_no_training_rows:{held_out}:{mode}")
    return np.vstack(x_parts), np.concatenate(y_parts)


def _predict(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    rv22: np.ndarray,
) -> np.ndarray:
    scaler = StandardScaler().fit(train_x)
    model = Ridge(alpha=RIDGE_ALPHA).fit(
        scaler.transform(train_x),
        train_y,
    )
    z_hat = model.predict(scaler.transform(test_x))
    prediction = rv22 * np.exp(z_hat)
    if np.any(~np.isfinite(prediction)) or np.any(prediction <= 0.0):
        raise RuntimeError("task101_transfer_invalid_prediction")
    return prediction


def _qlike(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> np.ndarray:
    if (
        np.any(~np.isfinite(actual))
        or np.any(~np.isfinite(predicted))
        or np.any(actual <= 0.0)
        or np.any(predicted <= 0.0)
    ):
        raise RuntimeError("task101_transfer_invalid_qlike_input")
    ratio = actual / predicted
    return ratio - np.log(ratio) - 1.0


def _evaluate(
    *,
    data: dict[str, PanelData],
    markets: dict[str, Market],
    held_out: str,
    test_start: date,
    test_end: date | None,
    origin_end: date | None,
) -> Evaluation:
    panel = data[held_out]
    test_mask = _eligible(panel) & np.array(
        [value >= test_start and (test_end is None or value <= test_end) for value in panel.dates],
        dtype=bool,
    )
    if not np.any(test_mask):
        raise RuntimeError(f"task101_transfer_no_test_rows:{held_out}:{test_start}")

    base_test = _design(
        panel.x_d[test_mask],
        panel.x_w[test_mask],
        markets[held_out],
        partial=False,
    )
    partial_test = _design(
        panel.x_d[test_mask],
        panel.x_w[test_mask],
        markets[held_out],
        partial=True,
    )
    actual = panel.target[test_mask]
    rv22 = panel.rv22[test_mask]

    losses: dict[Mode, np.ndarray] = {}
    for mode in ("global", "market", "partial"):
        train_x, train_y = _training_rows(
            data=data,
            markets=markets,
            held_out=held_out,
            mode=mode,
            maturity_before=test_start,
            origin_end=origin_end,
        )
        test_x = partial_test if mode == "partial" else base_test
        losses[mode] = _qlike(
            actual,
            _predict(
                train_x,
                train_y,
                test_x,
                rv22,
            ),
        )

    return Evaluation(
        dates=panel.dates[test_mask],
        global_qlike=losses["global"],
        market_qlike=losses["market"],
        partial_qlike=losses["partial"],
    )


def _run_final_holdout(
    *,
    data: dict[str, PanelData],
    markets: dict[str, Market],
    horizon: int,
) -> list[dict[str, object]]:
    evaluations = {
        symbol: _evaluate(
            data=data,
            markets=markets,
            held_out=symbol,
            test_start=EVALUATION_START_DATE,
            test_end=None,
            origin_end=TRAIN_END_DATE,
        )
        for symbol in data
    }

    rows = [
        _result_row(
            kind="symbol",
            name=symbol,
            market=markets[symbol],
            evaluation=evaluation,
        )
        for symbol, evaluation in evaluations.items()
    ]
    rows.extend(
        _scope_rows(
            evaluations=evaluations,
            markets=markets,
        )
    )
    for row in rows:
        row["horizon"] = horizon
        row["evaluation_start"] = EVALUATION_START_DATE.isoformat()
        row["training_origin_end"] = TRAIN_END_DATE.isoformat()
    return rows


def _run_expanding_folds(
    *,
    data: dict[str, PanelData],
    markets: dict[str, Market],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fold_id, fold_start, fold_end in FOLDS:
        evaluations = {
            symbol: _evaluate(
                data=data,
                markets=markets,
                held_out=symbol,
                test_start=fold_start,
                test_end=fold_end,
                origin_end=None,
            )
            for symbol in data
        }
        for row in _scope_rows(
            evaluations=evaluations,
            markets=markets,
        ):
            row["fold"] = fold_id
            row["start"] = fold_start.isoformat()
            row["end"] = fold_end.isoformat() if fold_end is not None else "end"
            row["horizon"] = 5
            rows.append(row)
    return rows


def _result_row(
    *,
    kind: str,
    name: str,
    market: str,
    evaluation: Evaluation,
) -> dict[str, object]:
    market_global = evaluation.market_qlike - evaluation.global_qlike
    partial_global = evaluation.partial_qlike - evaluation.global_qlike
    partial_market = evaluation.partial_qlike - evaluation.market_qlike
    mg = _moving_block_ci(market_global)
    pg = _moving_block_ci(partial_global)
    pm = _moving_block_ci(partial_market)
    return {
        "kind": kind,
        "name": name,
        "market": market,
        "n": evaluation.dates.size,
        "global_qlike": float(evaluation.global_qlike.mean()),
        "market_qlike": float(evaluation.market_qlike.mean()),
        "partial_qlike": float(evaluation.partial_qlike.mean()),
        "market_minus_global": mg[0],
        "market_global_ci_025": mg[1],
        "market_global_ci_975": mg[2],
        "partial_minus_global": pg[0],
        "partial_global_ci_025": pg[1],
        "partial_global_ci_975": pg[2],
        "partial_minus_market": pm[0],
        "partial_market_ci_025": pm[1],
        "partial_market_ci_975": pm[2],
    }


def _scope_rows(
    *,
    evaluations: dict[str, Evaluation],
    markets: dict[str, Market],
) -> list[dict[str, object]]:
    return [
        _scope_row(
            evaluations=evaluations,
            markets=markets,
            name="overall",
            market=None,
        ),
        _scope_row(
            evaluations=evaluations,
            markets=markets,
            name="us",
            market="us",
        ),
        _scope_row(
            evaluations=evaluations,
            markets=markets,
            name="taiwan",
            market="taiwan",
        ),
    ]


def _scope_row(
    *,
    evaluations: dict[str, Evaluation],
    markets: dict[str, Market],
    name: str,
    market: Market | None,
) -> dict[str, object]:
    per_date: dict[date, list[tuple[float, float, float]]] = {}
    for symbol, evaluation in evaluations.items():
        if market is not None and markets[symbol] != market:
            continue
        for current_date, global_loss, market_loss, partial_loss in zip(
            evaluation.dates,
            evaluation.global_qlike,
            evaluation.market_qlike,
            evaluation.partial_qlike,
            strict=True,
        ):
            per_date.setdefault(current_date, []).append(
                (
                    float(global_loss),
                    float(market_loss),
                    float(partial_loss),
                )
            )
    if not per_date:
        raise RuntimeError(f"task101_transfer_empty_scope:{name}")

    date_rows = np.array(
        [np.mean(per_date[current_date], axis=0) for current_date in sorted(per_date)],
        dtype=float,
    )
    synthetic = Evaluation(
        dates=np.array(sorted(per_date), dtype=object),
        global_qlike=date_rows[:, 0],
        market_qlike=date_rows[:, 1],
        partial_qlike=date_rows[:, 2],
    )
    return _result_row(
        kind="scope",
        name=name,
        market=market or "all",
        evaluation=synthetic,
    )


def _moving_block_ci(
    values: np.ndarray,
) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    if values.size < BOOTSTRAP_BLOCK_LENGTH:
        raise RuntimeError("task101_transfer_not_enough_bootstrap_rows")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = np.arange(values.size - BOOTSTRAP_BLOCK_LENGTH + 1)
    blocks_needed = math.ceil(values.size / BOOTSTRAP_BLOCK_LENGTH)
    means = np.empty(BOOTSTRAP_REPLICATES)

    for index in range(BOOTSTRAP_REPLICATES):
        chosen = rng.choice(
            starts,
            size=blocks_needed,
            replace=True,
        )
        sample = np.concatenate([values[start : start + BOOTSTRAP_BLOCK_LENGTH] for start in chosen])[
            : values.size
        ]
        means[index] = sample.mean()

    lower, upper = np.quantile(
        means,
        [0.025, 0.975],
    )
    return (
        float(values.mean()),
        float(lower),
        float(upper),
    )


def _write_csv(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        raise RuntimeError("task101_transfer_empty_output")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("task101_transfer_invalid_string")
    return value


if __name__ == "__main__":
    main()
