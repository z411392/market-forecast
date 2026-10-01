from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from arch import arch_model
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

Market = Literal["us", "taiwan"]

INPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-101-baseline-input"
)
PANEL_PATH = INPUT_ROOT / "panel" / "canonical-daily-panel.json"
US_ROOT = INPUT_ROOT / "us"
TAIWAN_ROOT = INPUT_ROOT / "taiwan"

OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-101-canonical-baselines"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
PER_SYMBOL_PATH = OUTPUT_ROOT / "per-symbol.csv"
BOOTSTRAP_PATH = OUTPUT_ROOT / "bootstrap.csv"
FORECASTS_PATH = OUTPUT_ROOT / "forecast-diagnostics.json"

SYMBOLS = ("GOOGL", "NVDA", "QQQ", "TSM", "2330", "2317", "2454")
US_SYMBOLS = frozenset(("GOOGL", "NVDA", "QQQ", "TSM"))
TAIWAN_SYMBOLS = frozenset(("2330", "2317", "2454"))
START_DATE = date(2022, 7, 18)
TRAIN_END = date(2025, 11, 25)
EVAL_START = date(2025, 12, 4)
HORIZON = 5
HAR_WEEK = 5
HAR_MONTH = 22
HAR_TRAIN_ROWS = 504
RIDGE_ALPHA = 1.0
EWMA_LAMBDA = 0.94
GARCH_WINDOW = 504
GARCH_REFIT_EVERY = 20
BOOTSTRAP_BLOCK = 20
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260926
EPS = 1e-12

MODEL_NAMES = (
    "global",
    "level_har",
    "log_har",
    "garch",
    "ewma",
    "naive",
)
COMPARISONS = (
    ("level_har", "global"),
    ("log_har", "level_har"),
    ("garch", "level_har"),
    ("ewma", "level_har"),
    ("naive", "level_har"),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Task #101 canonical mandatory baseline comparison."
    )
    parser.add_argument(
        "--non-garch-only",
        action="store_true",
        help=(
            "Run unaffected global/HAR/Log-HAR/EWMA/naive comparators "
            "after the preregistered GARCH path has failed closed."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    active_model_names = (
        tuple(name for name in MODEL_NAMES if name != "garch")
        if args.non_garch_only
        else MODEL_NAMES
    )
    active_comparisons = (
        tuple(
            pair
            for pair in COMPARISONS
            if "garch" not in pair
        )
        if args.non_garch_only
        else COMPARISONS
    )

    panel = _load_json(PANEL_PATH)
    _validate_panel(panel)

    close_maps = {
        **_load_us_closes(),
        **_load_taiwan_closes(),
    }
    data = {
        symbol: _build_symbol_data(
            symbol,
            panel["daily_values"][symbol],
            close_maps[symbol],
        )
        for symbol in SYMBOLS
    }

    global_forecasts = _global_ridge_forecasts(data)
    forecast_diag: dict[str, Any] = {}
    per_symbol_rows: list[dict[str, object]] = []
    scored_by_symbol: dict[str, dict[str, np.ndarray]] = {}

    for symbol in SYMBOLS:
        item = data[symbol]
        level_har = _har_forecast(item, use_log=False)
        log_har = _har_forecast(item, use_log=True)
        ewma = _ewma_forecast(item["returns"])
        if args.non_garch_only:
            garch = None
            garch_diag = {
                "status": "failed_closed_not_reexecuted",
                "reference": (
                    "docs/research/experiments/"
                    "task-101-canonical-garch-failure-reference.json"
                ),
            }
        else:
            garch, garch_diag = _garch_forecast(
                symbol,
                item["returns"],
            )
        naive = item["rv5"].copy()
        global_forecast = global_forecasts[symbol]

        forecasts = {
            "global": global_forecast,
            "level_har": level_har,
            "log_har": log_har,
            "ewma": ewma,
            "naive": naive,
        }
        if garch is not None:
            forecasts["garch"] = garch
        common = (
            np.array(
                [value >= EVAL_START for value in item["dates"]],
                dtype=bool,
            )
            & np.isfinite(item["y5"])
            & (item["y5"] > 0.0)
        )
        for forecast in forecasts.values():
            common &= np.isfinite(forecast) & (forecast > 0.0)

        if int(common.sum()) < BOOTSTRAP_BLOCK:
            raise RuntimeError(
                f"task101_baseline_insufficient_common_rows:{symbol}:"
                f"{int(common.sum())}"
            )

        actual = item["y5"][common]
        losses = {
            name: _qlike(actual, forecast[common])
            for name, forecast in forecasts.items()
        }
        scored_by_symbol[symbol] = {
            "dates": item["dates"][common],
            **losses,
        }

        per_symbol_rows.append(
            {
                "symbol": symbol,
                "market": item["market"],
                "n_eval": int(common.sum()),
                **{
                    f"{name}_qlike": float(loss.mean())
                    for name, loss in losses.items()
                },
            }
        )
        forecast_diag[symbol] = {
            "market": item["market"],
            "return_count": int(np.isfinite(item["returns"]).sum()),
            "missing_rv_count": int((~np.isfinite(item["rv"])).sum()),
            "common_eval_count": int(common.sum()),
            "garch": garch_diag,
            "forecast_available_count": {
                name: int(np.isfinite(values).sum())
                for name, values in forecasts.items()
            },
        }

    bootstrap_rows = _bootstrap_rows(
        scored_by_symbol,
        {
            symbol: data[symbol]["market"]
            for symbol in SYMBOLS
        },
        active_model_names,
        active_comparisons,
    )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    _write_csv(PER_SYMBOL_PATH, per_symbol_rows)
    _write_csv(BOOTSTRAP_PATH, bootstrap_rows)
    FORECASTS_PATH.write_text(
        json.dumps(
            forecast_diag,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "artifact_version": "task-101-canonical-baselines-v1",
        "task": 101,
        "slice": "S2-mandatory-baselines",
        "status": (
            "accepted_non_garch_subset"
            if args.non_garch_only
            else "accepted"
        ),
        "garch_status": (
            "failed_closed_not_reexecuted"
            if args.non_garch_only
            else "included"
        ),
        "input_sha256": {
            "canonical_panel": _sha256(PANEL_PATH),
        },
        "protocol": {
            "evaluation_start": EVAL_START.isoformat(),
            "horizon_sessions": HORIZON,
            "har_train_rows": HAR_TRAIN_ROWS,
            "ewma_lambda": EWMA_LAMBDA,
            "garch_window_returns": GARCH_WINDOW,
            "garch_refit_every_observed_sessions": GARCH_REFIT_EVERY,
            "garch_estimator": "arch Gaussian QMLE",
            "bootstrap_block": BOOTSTRAP_BLOCK,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "common_scoring_rows": True,
        },
        "provenance_exception": {
            "legacy_pine_fixed_grid_reproduced": False,
            "reason": (
                "legacy Phase 4A Pine source bytes and exact fixed "
                "alpha-persistence grid are unavailable"
            ),
            "replacement": (
                "same zero-mean GARCH(1,1) class, trailing 504 returns, "
                "20-observed-session refit cadence, Gaussian QMLE via arch"
            ),
        },
        "per_symbol": per_symbol_rows,
        "bootstrap": bootstrap_rows,
        "forecast_diagnostics_sha256": _sha256(FORECASTS_PATH),
        "per_symbol_sha256": _sha256(PER_SYMBOL_PATH),
        "bootstrap_sha256": _sha256(BOOTSTRAP_PATH),
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


def _validate_panel(panel: dict[str, Any]) -> None:
    if (
        panel.get("artifact_version")
        != "task-101-canonical-daily-panel-v1"
        or panel.get("measurement_frozen") is not True
        or panel.get("measurement_manifest_version")
        != "cross-market-rv-measurement-target-manifest-v2"
    ):
        raise RuntimeError("task101_baseline_invalid_panel_identity")
    daily = panel.get("daily_values")
    if not isinstance(daily, dict) or set(daily) != set(SYMBOLS):
        raise RuntimeError("task101_baseline_unexpected_universe")


def _load_us_closes() -> dict[str, dict[date, float]]:
    result = {symbol: {} for symbol in US_SYMBOLS}

    for receipt_path in US_ROOT.glob(
        "evidence/alpaca/*/*/*/*/acceptance-receipt.json"
    ):
        receipt = _load_json(receipt_path)
        symbol = receipt.get("source_symbol")
        if symbol not in US_SYMBOLS:
            continue
        session_date = date.fromisoformat(
            _require_str(receipt.get("session_date"))
        )
        raw_path = receipt_path.parent / "raw-response.bin"
        raw = raw_path.read_bytes()
        expected_sha = _require_str(
            receipt.get("raw_artifact_sha256")
        )
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            raise RuntimeError(
                f"task101_baseline_us_raw_hash_mismatch:{symbol}:"
                f"{session_date}"
            )
        payload = json.loads(raw)
        close = _alpaca_last_close(payload, symbol)
        _insert_close(result[symbol], session_date, close)

    diagnostics_root = US_ROOT / "diagnostics"
    if diagnostics_root.exists():
        for raw_path in diagnostics_root.glob("*/*/*/*.json"):
            symbol = raw_path.parents[2].name
            if symbol not in US_SYMBOLS:
                continue
            session_date = date.fromisoformat(
                raw_path.parents[1].name
            )
            raw = raw_path.read_bytes()
            expected_sha = raw_path.stem
            if hashlib.sha256(raw).hexdigest() != expected_sha:
                raise RuntimeError(
                    "task101_baseline_us_diagnostic_hash_mismatch:"
                    f"{symbol}:{session_date}"
                )
            payload = json.loads(raw)
            close = _alpaca_last_close(payload, symbol)
            _insert_close(result[symbol], session_date, close)

    for symbol in US_SYMBOLS:
        if date(2022, 7, 15) not in result[symbol]:
            raise RuntimeError(
                f"task101_baseline_us_prior_close_missing:{symbol}"
            )
    return result


def _alpaca_last_close(
    payload: object,
    symbol: str,
) -> float:
    if not isinstance(payload, dict):
        raise RuntimeError("task101_baseline_alpaca_not_object")
    if payload.get("symbol") != symbol:
        raise RuntimeError("task101_baseline_alpaca_symbol_mismatch")
    bars = payload.get("bars")
    if not isinstance(bars, list) or not bars:
        raise RuntimeError("task101_baseline_alpaca_empty_bars")
    last = bars[-1]
    if not isinstance(last, dict):
        raise RuntimeError("task101_baseline_alpaca_invalid_bar")
    return _positive_float(
        last.get("c"),
        "task101_baseline_alpaca_invalid_close",
    )


def _load_taiwan_closes() -> dict[str, dict[date, float]]:
    result = {symbol: {} for symbol in TAIWAN_SYMBOLS}
    for chunk_path in TAIWAN_ROOT.glob("chunks/*/*.json"):
        symbol = chunk_path.parent.name
        if symbol not in TAIWAN_SYMBOLS:
            continue
        chunk = _load_json(chunk_path)
        if (
            chunk.get("provider") != "shioaji"
            or chunk.get("symbol") != symbol
        ):
            raise RuntimeError(
                f"task101_baseline_tw_chunk_identity:{symbol}"
            )
        payload = chunk.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError("task101_baseline_tw_payload_missing")
        ts = payload.get("ts")
        closes = payload.get("Close")
        if not isinstance(ts, list) or not isinstance(closes, list):
            raise RuntimeError("task101_baseline_tw_payload_shape")
        if len(ts) != len(closes):
            raise RuntimeError("task101_baseline_tw_payload_length")

        for raw_ts, raw_close in zip(ts, closes, strict=True):
            if type(raw_ts) is not int:
                raise RuntimeError(
                    "task101_baseline_tw_invalid_timestamp"
                )
            seconds, nanoseconds = divmod(
                raw_ts,
                1_000_000_000,
            )
            if nanoseconds != 0:
                raise RuntimeError(
                    "task101_baseline_tw_timestamp_precision"
                )
            wall = datetime.fromtimestamp(
                seconds,
                tz=timezone.utc,
            )
            if wall.hour == 13 and wall.minute == 30:
                close = _positive_float(
                    raw_close,
                    "task101_baseline_tw_invalid_close",
                )
                _insert_close(result[symbol], wall.date(), close)

    for symbol in TAIWAN_SYMBOLS:
        if date(2022, 7, 15) not in result[symbol]:
            raise RuntimeError(
                f"task101_baseline_tw_prior_close_missing:{symbol}"
            )
    return result


def _insert_close(
    target: dict[date, float],
    session_date: date,
    close: float,
) -> None:
    previous = target.get(session_date)
    if previous is not None and not math.isclose(
        previous,
        close,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise RuntimeError(
            f"task101_baseline_conflicting_close:{session_date}"
        )
    target[session_date] = close


def _build_symbol_data(
    symbol: str,
    entry: object,
    closes: dict[date, float],
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise RuntimeError("task101_baseline_invalid_entry")
    market = _market(entry.get("market"))
    rows = entry.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("task101_baseline_missing_rows")

    dates: list[date] = []
    rv_values: list[float] = []
    previous: date | None = None
    for raw in rows:
        if not isinstance(raw, dict):
            raise RuntimeError("task101_baseline_invalid_row")
        session_date = date.fromisoformat(
            _require_str(raw.get("session_date"))
        )
        if previous is not None and session_date <= previous:
            raise RuntimeError(
                f"task101_baseline_non_increasing_dates:{symbol}"
            )
        previous = session_date
        dates.append(session_date)
        value = raw.get("whole_day_variance")
        if value is None:
            rv_values.append(math.nan)
        else:
            rv_values.append(
                _positive_float(
                    value,
                    f"task101_baseline_invalid_rv:{symbol}",
                )
            )

    date_array = np.array(dates, dtype=object)
    rv = np.array(rv_values, dtype=float)
    rv5 = _rolling_mean(rv, HAR_WEEK)
    rv22 = _rolling_mean(rv, HAR_MONTH)
    y5 = _future_mean(rv, HORIZON)

    returns = np.full(rv.size, np.nan)
    observed_close_dates = sorted(
        value
        for value in closes
        if value <= dates[-1]
    )
    if not observed_close_dates:
        raise RuntimeError(
            f"task101_baseline_no_close_history:{symbol}"
        )
    previous_close: float | None = None
    return_by_date: dict[date, float] = {}
    for current_date in observed_close_dates:
        current_close = closes[current_date]
        if previous_close is not None:
            return_by_date[current_date] = math.log(
                current_close / previous_close
            )
        previous_close = current_close

    for index, current_date in enumerate(dates):
        value = return_by_date.get(current_date)
        if value is not None:
            returns[index] = value

    return {
        "symbol": symbol,
        "market": market,
        "dates": date_array,
        "rv": rv,
        "rv5": rv5,
        "rv22": rv22,
        "y5": y5,
        "returns": returns,
    }


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


def _future_mean(
    values: np.ndarray,
    horizon: int,
) -> np.ndarray:
    result = np.full(values.size, np.nan)
    for index in range(values.size - horizon):
        future = values[index + 1 : index + horizon + 1]
        if np.all(np.isfinite(future)):
            result[index] = float(future.mean())
    return result


def _har_forecast(
    item: dict[str, Any],
    *,
    use_log: bool,
) -> np.ndarray:
    rv = item["rv"]
    rv5 = item["rv5"]
    rv22 = item["rv22"]
    y5 = item["y5"]

    if use_log:
        with np.errstate(divide="ignore", invalid="ignore"):
            d = np.log(rv)
            w = np.log(rv5)
            m = np.log(rv22)
            target = np.log(y5)
    else:
        d = rv.copy()
        w = rv5.copy()
        m = rv22.copy()
        target = y5.copy()

    forecast = np.full(rv.size, np.nan)
    eligible_origin = (
        np.isfinite(d)
        & np.isfinite(w)
        & np.isfinite(m)
        & np.isfinite(target)
    )

    for index in range(rv.size):
        current = np.array(
            [d[index], w[index], m[index]],
            dtype=float,
        )
        if not np.all(np.isfinite(current)):
            continue

        matured_end = index - HORIZON
        if matured_end < 0:
            continue
        candidates = np.flatnonzero(
            eligible_origin[: matured_end + 1]
        )
        if candidates.size < HAR_TRAIN_ROWS:
            continue
        train_idx = candidates[-HAR_TRAIN_ROWS:]
        x = np.column_stack(
            (
                d[train_idx],
                w[train_idx],
                m[train_idx],
            )
        )
        y = target[train_idx]

        means = x.mean(axis=0)
        mean_y = float(y.mean())
        centered = x - means
        centered_y = y - mean_y
        covariance = centered.T @ centered / HAR_TRAIN_ROWS
        covariance_y = (
            centered.T @ centered_y / HAR_TRAIN_ROWS
        )
        beta = np.linalg.pinv(covariance) @ covariance_y
        intercept = mean_y - float(beta @ means)
        prediction = intercept + float(beta @ current)
        if use_log:
            prediction = math.exp(prediction)
        if math.isfinite(prediction) and prediction > 0.0:
            forecast[index] = max(prediction, EPS)
    return forecast


def _ewma_forecast(
    returns: np.ndarray,
) -> np.ndarray:
    result = np.full(returns.size, np.nan)
    state: float | None = None
    for index, value in enumerate(returns):
        if not math.isfinite(float(value)):
            continue
        squared = float(value) ** 2
        if state is None:
            state = squared
        else:
            state = (
                EWMA_LAMBDA * state
                + (1.0 - EWMA_LAMBDA) * squared
            )
        result[index] = max(state, EPS)
    return result


def _garch_forecast(
    symbol: str,
    returns: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    result = np.full(returns.size, np.nan)
    observed_history: list[float] = []
    params: tuple[float, float, float] | None = None
    h_current: float | None = None
    last_refit_observed_index: int | None = None
    observed_index = -1
    refits: list[dict[str, Any]] = []

    for index, raw_return in enumerate(returns):
        if not math.isfinite(float(raw_return)):
            continue
        observed_index += 1
        scaled_return = float(raw_return) * 100.0
        observed_history.append(scaled_return)
        if len(observed_history) < GARCH_WINDOW:
            continue

        need_refit = (
            params is None
            or last_refit_observed_index is None
            or observed_index - last_refit_observed_index
            >= GARCH_REFIT_EVERY
        )
        if need_refit:
            sample = np.asarray(
                observed_history[-GARCH_WINDOW:],
                dtype=float,
            )
            model = arch_model(
                sample,
                mean="Zero",
                vol="GARCH",
                p=1,
                q=1,
                dist="normal",
                rescale=False,
            )
            fit = model.fit(
                disp="off",
                show_warning=False,
                update_freq=0,
            )
            if fit.convergence_flag != 0:
                raise RuntimeError(
                    "task101_baseline_garch_nonconverged:"
                    f"{symbol}:observed_index={observed_index}:"
                    f"flag={fit.convergence_flag}"
                )
            omega = float(fit.params["omega"])
            alpha = float(fit.params["alpha[1]"])
            beta = float(fit.params["beta[1]"])
            if (
                not all(
                    math.isfinite(value)
                    for value in (omega, alpha, beta)
                )
                or omega <= 0.0
                or alpha < 0.0
                or beta < 0.0
                or alpha + beta >= 1.0
            ):
                raise RuntimeError(
                    "task101_baseline_garch_invalid_parameters:"
                    f"{symbol}:observed_index={observed_index}:"
                    f"omega={omega:.17g}:alpha={alpha:.17g}:"
                    f"beta={beta:.17g}:"
                    f"persistence={alpha + beta:.17g}"
                )
            params = (omega, alpha, beta)
            h_current = float(
                fit.conditional_volatility[-1] ** 2
            )
            if not math.isfinite(h_current) or h_current <= 0.0:
                raise RuntimeError(
                    "task101_baseline_garch_invalid_state:"
                    f"{symbol}:observed_index={observed_index}:"
                    f"h={h_current:.17g}"
                )
            last_refit_observed_index = observed_index
            refits.append(
                {
                    "array_index": index,
                    "observed_return_index": observed_index,
                    "omega": omega,
                    "alpha": alpha,
                    "beta": beta,
                    "persistence": alpha + beta,
                }
            )

        if params is None or h_current is None:
            continue
        omega, alpha, beta = params
        h1 = (
            omega
            + alpha * scaled_return * scaled_return
            + beta * h_current
        )
        if not math.isfinite(h1) or h1 <= 0.0:
            raise RuntimeError(
                "task101_baseline_garch_invalid_one_step:"
                f"{symbol}:observed_index={observed_index}:"
                f"h1={h1:.17g}"
            )

        persistence = alpha + beta
        horizon_values = [h1]
        next_h = h1
        for _ in range(1, HORIZON):
            next_h = omega + persistence * next_h
            horizon_values.append(next_h)
        average_variance = (
            float(np.mean(horizon_values)) / 10000.0
        )
        if not math.isfinite(average_variance) or average_variance <= 0.0:
            raise RuntimeError(
                "task101_baseline_garch_invalid_forecast"
            )
        result[index] = max(average_variance, EPS)
        h_current = h1

    return result, {
        "refit_count": len(refits),
        "first_refit": refits[0] if refits else None,
        "last_refit": refits[-1] if refits else None,
    }


def _global_ridge_forecasts(
    data: dict[str, dict[str, Any]],
) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for held_out in SYMBOLS:
        x_parts: list[np.ndarray] = []
        y_parts: list[np.ndarray] = []
        for symbol in SYMBOLS:
            if symbol == held_out:
                continue
            item = data[symbol]
            with np.errstate(divide="ignore", invalid="ignore"):
                x_d = np.log(item["rv"] / item["rv22"])
                x_w = np.log(item["rv5"] / item["rv22"])
                z = np.log(item["y5"] / item["rv22"])
            before = np.array(
                [value <= TRAIN_END for value in item["dates"]],
                dtype=bool,
            )
            mask = (
                before
                & np.isfinite(x_d)
                & np.isfinite(x_w)
                & np.isfinite(z)
            )
            x_parts.append(
                np.column_stack((x_d[mask], x_w[mask]))
            )
            y_parts.append(z[mask])

        train_x = np.vstack(x_parts)
        train_y = np.concatenate(y_parts)
        scaler = StandardScaler().fit(train_x)
        model = Ridge(alpha=RIDGE_ALPHA).fit(
            scaler.transform(train_x),
            train_y,
        )

        held = data[held_out]
        with np.errstate(divide="ignore", invalid="ignore"):
            held_x_d = np.log(held["rv"] / held["rv22"])
            held_x_w = np.log(held["rv5"] / held["rv22"])
        forecast = np.full(held["rv"].size, np.nan)
        eligible = (
            np.isfinite(held_x_d)
            & np.isfinite(held_x_w)
            & np.isfinite(held["rv22"])
        )
        test_x = np.column_stack(
            (held_x_d[eligible], held_x_w[eligible])
        )
        normalized = model.predict(
            scaler.transform(test_x)
        )
        predicted = held["rv22"][eligible] * np.exp(normalized)
        forecast[eligible] = predicted
        result[held_out] = forecast
    return result


def _bootstrap_rows(
    scored: dict[str, dict[str, np.ndarray]],
    markets: dict[str, Market],
    model_names: tuple[str, ...],
    comparisons: tuple[tuple[str, str], ...],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for scope, market in (
        ("overall", None),
        ("us", "us"),
        ("taiwan", "taiwan"),
    ):
        date_values: dict[date, dict[str, list[float]]] = {}
        for symbol, item in scored.items():
            if market is not None and markets[symbol] != market:
                continue
            for row_index, session_date in enumerate(item["dates"]):
                target = date_values.setdefault(
                    session_date,
                    {
                        name: []
                        for name in model_names
                    },
                )
                for name in model_names:
                    target[name].append(
                        float(item[name][row_index])
                    )

        ordered_dates = sorted(date_values)
        mean_losses = {
            name: np.array(
                [
                    float(
                        np.mean(
                            date_values[current_date][name]
                        )
                    )
                    for current_date in ordered_dates
                ],
                dtype=float,
            )
            for name in model_names
        }

        for first, second in comparisons:
            delta = mean_losses[first] - mean_losses[second]
            mean, lower, upper = _moving_block_ci(delta)
            rows.append(
                {
                    "scope": scope,
                    "comparison": f"{first}_minus_{second}",
                    "n_dates": len(ordered_dates),
                    "first_qlike": float(
                        mean_losses[first].mean()
                    ),
                    "second_qlike": float(
                        mean_losses[second].mean()
                    ),
                    "mean_delta": mean,
                    "ci_025": lower,
                    "ci_975": upper,
                }
            )
    return rows


def _moving_block_ci(
    values: np.ndarray,
) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    if values.size < BOOTSTRAP_BLOCK:
        raise RuntimeError(
            "task101_baseline_not_enough_bootstrap_rows"
        )
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = np.arange(
        values.size - BOOTSTRAP_BLOCK + 1
    )
    blocks_needed = math.ceil(
        values.size / BOOTSTRAP_BLOCK
    )
    means = np.empty(BOOTSTRAP_REPS)
    for index in range(BOOTSTRAP_REPS):
        chosen = rng.choice(
            starts,
            size=blocks_needed,
            replace=True,
        )
        sample = np.concatenate(
            [
                values[
                    start : start + BOOTSTRAP_BLOCK
                ]
                for start in chosen
            ]
        )[: values.size]
        means[index] = sample.mean()
    lower, upper = np.quantile(
        means,
        [0.025, 0.975],
    )
    return float(values.mean()), float(lower), float(upper)


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
        raise RuntimeError(
            "task101_baseline_invalid_qlike_input"
        )
    ratio = actual / predicted
    return ratio - np.log(ratio) - 1.0


def _market(value: object) -> Market:
    if value == "us":
        return "us"
    if value == "taiwan":
        return "taiwan"
    raise RuntimeError("task101_baseline_invalid_market")


def _positive_float(
    value: object,
    error: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise RuntimeError(error)
    return float(value)


def _require_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("task101_baseline_invalid_string")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(
            f"task101_baseline_json_not_object:{path}"
        )
    return value


def _write_csv(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        raise RuntimeError("task101_baseline_empty_csv")
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


if __name__ == "__main__":
    main()
