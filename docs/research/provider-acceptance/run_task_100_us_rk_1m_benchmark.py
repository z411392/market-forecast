import json
import math
import statistics
from bisect import bisect_right
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from libs.market_data.services.decode_alpaca_stock_bars import (
    decode_alpaca_stock_bars,
)

ESTIMATOR_VERSION = "us-rk-parzen-1m-v1"
INPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-100-us-rk-input"
)
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-100-us-rk-benchmark"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"
GRID_MINUTES = (5, 10, 15)
ENDPOINT_JITTER_M = 2
BANDWIDTH_CONSTANT = 3.5134
NOISE_TARGET_SECONDS = 120
SPARSE_INTERVAL_SECONDS = 1200
SPARSE_PHASE_SHIFT_SECONDS = 60


def main() -> None:
    _self_check_math()
    evidence = _load_evidence()
    fixed = _load_fixed_grid_daily()

    symbols = ("AAPL", "NVDA")
    sessions = _validate_sessions(evidence, symbols)
    audit_sessions = sessions[1:]

    metrics: dict[str, dict[str, dict[str, float | int]]] = {}
    daily_output: dict[str, list[dict[str, Any]]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}

    for symbol in symbols:
        previous_close = evidence[(symbol, sessions[0])][-1]["close"]
        rows: list[dict[str, Any]] = []
        bandwidths: list[int] = []
        q_values: list[int] = []
        noise_values: list[float] = []
        sparse_values: list[float] = []

        for session_date in audit_sessions:
            bars = evidence[(symbol, session_date)]
            fixed_row = fixed[(symbol, session_date)]
            opening = bars[0]["open"]
            overnight_return = math.log(opening / previous_close)
            overnight_variance = overnight_return * overnight_return

            if not math.isclose(
                overnight_return,
                float(fixed_row["overnight_log_return"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise RuntimeError(
                    f"task100_overnight_mismatch:{symbol}:{session_date}"
                )

            timestamps = (
                bars[0]["bar_start_utc"],
                *tuple(
                    bar["bar_start_utc"] + timedelta(minutes=1)
                    for bar in bars
                ),
            )
            log_prices = (
                math.log(opening),
                *tuple(math.log(bar["close"]) for bar in bars),
            )
            q = _select_q(timestamps, NOISE_TARGET_SECONDS)
            noise = _noise_variance(log_prices, q)
            sparse = _sparse_rv(
                timestamps,
                log_prices,
                SPARSE_INTERVAL_SECONDS,
                SPARSE_PHASE_SHIFT_SECONDS,
            )
            return_count = len(log_prices) - 3
            bandwidth = _bandwidth(
                noise,
                sparse,
                return_count,
                BANDWIDTH_CONSTANT,
            )
            intraday_rk = _parzen_rk(
                log_prices,
                bandwidth,
                ENDPOINT_JITTER_M,
            )
            whole_day_rk = intraday_rk + overnight_variance
            if whole_day_rk <= 0.0:
                raise RuntimeError(
                    f"task100_nonpositive_rk:{symbol}:{session_date}"
                )

            row: dict[str, Any] = {
                "session_date": session_date,
                "rk_whole_day_variance": whole_day_rk,
                "intraday_rk": intraday_rk,
                "overnight_variance": overnight_variance,
                "q": q,
                "noise_variance": noise,
                "sparse_realized_variance": sparse,
                "bandwidth": bandwidth,
            }
            for interval in GRID_MINUTES:
                row[f"{interval}m_whole_day_variance"] = float(
                    fixed_row[f"{interval}m"]["whole_day_variance"]
                )
            rows.append(row)
            bandwidths.append(bandwidth)
            q_values.append(q)
            noise_values.append(noise)
            sparse_values.append(sparse)
            previous_close = bars[-1]["close"]

        metrics[symbol] = {
            f"{interval}m": _summarize_grid(rows, interval)
            for interval in GRID_MINUTES
        }
        daily_output[symbol] = [_serialize_row(row) for row in rows]
        diagnostics[symbol] = {
            "bandwidth_min": min(bandwidths),
            "bandwidth_median": statistics.median(bandwidths),
            "bandwidth_max": max(bandwidths),
            "q_values": sorted(set(q_values)),
            "noise_variance_median": statistics.median(noise_values),
            "sparse_realized_variance_median": statistics.median(
                sparse_values
            ),
            "top_abs_log_gap_sessions": {
                f"{interval}m": _top_gaps(rows, interval)
                for interval in GRID_MINUTES
            },
        }

    panel = _panel_medians(metrics, symbols)
    decision = _decision(metrics, panel, symbols)
    summary = {
        "artifact_version": "task-100-us-rk-benchmark-v1",
        "task": 100,
        "parent_task": 12,
        "status": "accepted",
        "estimator": {
            "version": ESTIMATOR_VERSION,
            "kernel": "parzen",
            "endpoint_jitter_m": ENDPOINT_JITTER_M,
            "bandwidth_constant": BANDWIDTH_CONSTANT,
            "noise_target_seconds": NOISE_TARGET_SECONDS,
            "sparse_interval_seconds": SPARSE_INTERVAL_SECONDS,
            "sparse_phase_shift_seconds": SPARSE_PHASE_SHIFT_SECONDS,
            "input": "accepted_split_adjusted_alpaca_sip_1m",
        },
        "audit_window": {
            "prior_session": sessions[0].isoformat(),
            "first": audit_sessions[0].isoformat(),
            "last": audit_sessions[-1].isoformat(),
            "audit_sessions_per_symbol": len(audit_sessions),
            "symbols": list(symbols),
        },
        "metrics": metrics,
        "panel_medians": panel,
        "diagnostics": diagnostics,
        "decision": decision,
        "self_check": "pass",
        "forecast_score_used": False,
    }
    _write_json(SUMMARY_PATH, summary)
    _write_json(
        DAILY_PATH,
        {
            "artifact_version": "task-100-us-rk-daily-v1",
            "estimator_version": ESTIMATOR_VERSION,
            "daily_values": daily_output,
        },
    )


def _load_evidence() -> dict[tuple[str, str], tuple[dict[str, Any], ...]]:
    result: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {}
    receipts = sorted(
        INPUT_ROOT.glob(
            "evidence/alpaca/*/*/*/*/acceptance-receipt.json"
        )
    )
    if len(receipts) != 506:
        raise RuntimeError(
            f"task100_unexpected_receipt_count:{len(receipts)}"
        )

    for receipt_path in receipts:
        receipt = _load_json(receipt_path)
        if receipt["provider"] != "alpaca":
            raise RuntimeError("task100_wrong_provider")
        if receipt["price_basis"] != "split_adjusted":
            raise RuntimeError("task100_wrong_price_basis")

        raw_path = receipt_path.parent / "raw-response.bin"
        raw = raw_path.read_bytes()
        if sha256(raw).hexdigest() != receipt["raw_artifact_sha256"]:
            raise RuntimeError("task100_raw_hash_mismatch")
        payload = json.loads(raw)
        bars = decode_alpaca_stock_bars(
            payload=payload,
            expected_source_symbol=receipt["source_symbol"],
            security=receipt["security"],
            price_basis="split_adjusted",
        )
        if len(bars) != receipt["observed_minute_count"]:
            raise RuntimeError("task100_bar_count_mismatch")

        key = (receipt["source_symbol"], receipt["session_date"])
        if key in result:
            raise RuntimeError("task100_duplicate_symbol_session")
        result[key] = bars

    return result


def _load_fixed_grid_daily() -> dict[tuple[str, str], dict[str, Any]]:
    payload = _load_json(INPUT_ROOT / "daily-values.json")
    daily_values = payload["daily_values"]
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for symbol in ("AAPL", "NVDA"):
        for row in daily_values[symbol]:
            result[(symbol, row["session_date"])] = row
    return result


def _validate_sessions(
    evidence: dict[tuple[str, str], tuple[dict[str, Any], ...]],
    symbols: tuple[str, ...],
) -> tuple[str, ...]:
    by_symbol = {
        symbol: tuple(
            sorted(
                session
                for item_symbol, session in evidence
                if item_symbol == symbol
            )
        )
        for symbol in symbols
    }
    sessions = by_symbol[symbols[0]]
    if len(sessions) != 253:
        raise RuntimeError("task100_unexpected_session_count")
    if any(by_symbol[symbol] != sessions for symbol in symbols[1:]):
        raise RuntimeError("task100_cross_symbol_session_mismatch")
    return sessions


def _select_q(
    timestamps: tuple[datetime, ...],
    target_spacing_seconds: int,
) -> int:
    elapsed = (timestamps[-1] - timestamps[0]).total_seconds()
    if elapsed <= 0.0:
        raise RuntimeError("task100_invalid_elapsed")
    mean_gap = elapsed / (len(timestamps) - 1)
    raw = target_spacing_seconds / mean_gap
    return max(1, min(math.floor(raw + 0.5), len(timestamps) - 1))


def _noise_variance(log_prices: tuple[float, ...], q: int) -> float:
    estimates: list[float] = []
    for offset in range(q):
        subgrid = log_prices[offset::q]
        if len(subgrid) < 2:
            continue
        returns = tuple(
            current - previous
            for previous, current in zip(subgrid, subgrid[1:])
        )
        nonzero = tuple(value for value in returns if value != 0.0)
        if not nonzero:
            estimates.append(0.0)
        else:
            rv = math.fsum(value * value for value in returns)
            estimates.append(rv / (2.0 * len(nonzero)))
    if not estimates:
        raise RuntimeError("task100_no_noise_estimate")
    return math.fsum(estimates) / len(estimates)


def _sparse_rv(
    timestamps: tuple[datetime, ...],
    log_prices: tuple[float, ...],
    interval_seconds: int,
    phase_shift_seconds: int,
) -> float:
    estimates: list[float] = []
    start = timestamps[0]
    end = timestamps[-1]
    for offset in range(0, interval_seconds, phase_shift_seconds):
        grid_time = start + timedelta(seconds=offset)
        synchronized: list[float] = []
        while grid_time <= end:
            index = bisect_right(timestamps, grid_time) - 1
            if index >= 0:
                synchronized.append(log_prices[index])
            grid_time += timedelta(seconds=interval_seconds)
        if len(synchronized) < 2:
            continue
        returns = tuple(
            current - previous
            for previous, current in zip(
                synchronized, synchronized[1:]
            )
        )
        estimates.append(
            math.fsum(value * value for value in returns)
        )
    if not estimates:
        raise RuntimeError("task100_no_sparse_phase")
    return math.fsum(estimates) / len(estimates)


def _bandwidth(
    noise: float,
    sparse: float,
    return_count: int,
    constant: float,
) -> int:
    if noise == 0.0:
        return 1
    if sparse <= 0.0:
        raise RuntimeError("task100_invalid_sparse_rv")
    xi = math.sqrt(noise / sparse)
    raw = constant * xi ** (4.0 / 5.0) * return_count ** (3.0 / 5.0)
    return max(1, min(math.ceil(raw), return_count - 1))


def _jitter(
    log_prices: tuple[float, ...],
    m: int,
) -> tuple[float, ...]:
    if m != 2 or len(log_prices) < 4:
        raise RuntimeError("task100_invalid_jitter_input")
    first = math.fsum(log_prices[:m]) / m
    last = math.fsum(log_prices[-m:]) / m
    return (first, *log_prices[m:-m], last)


def _parzen_weight(x: float) -> float:
    if 0.0 <= x <= 0.5:
        return 1.0 - 6.0 * x * x + 6.0 * x * x * x
    if 0.5 < x <= 1.0:
        return 2.0 * (1.0 - x) ** 3
    return 0.0


def _autocovariance(returns: tuple[float, ...], lag: int) -> float:
    return math.fsum(
        returns[index] * returns[index - lag]
        for index in range(lag, len(returns))
    )


def _parzen_rk(
    log_prices: tuple[float, ...],
    bandwidth: int,
    m: int,
) -> float:
    jittered = _jitter(log_prices, m)
    returns = tuple(
        current - previous
        for previous, current in zip(jittered, jittered[1:])
    )
    result = _autocovariance(returns, 0)
    result += math.fsum(
        2.0
        * _parzen_weight(lag / (bandwidth + 1.0))
        * _autocovariance(returns, lag)
        for lag in range(1, min(bandwidth, len(returns) - 1) + 1)
    )
    if result < 0.0:
        if math.isclose(result, 0.0, abs_tol=1e-15):
            return 0.0
        raise RuntimeError("task100_negative_rk")
    return result


def _summarize_grid(
    rows: list[dict[str, Any]],
    interval: int,
) -> dict[str, float | int]:
    fixed = np.asarray(
        [row[f"{interval}m_whole_day_variance"] for row in rows],
        dtype=float,
    )
    rk = np.asarray(
        [row["rk_whole_day_variance"] for row in rows],
        dtype=float,
    )
    log_fixed = np.log(fixed)
    log_rk = np.log(rk)
    gap = log_fixed - log_rk
    spearman = float(spearmanr(fixed, rk).statistic)
    return {
        "n": len(rows),
        "geometric_bias_pct": (
            math.exp(float(np.mean(gap))) - 1.0
        )
        * 100.0,
        "mean_abs_log_gap": float(np.mean(np.abs(gap))),
        "pearson_log": float(
            np.corrcoef(log_fixed, log_rk)[0, 1]
        ),
        "spearman": spearman,
        "median_ratio": float(np.median(fixed / rk)),
    }


def _top_gaps(
    rows: list[dict[str, Any]],
    interval: int,
) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        fixed = row[f"{interval}m_whole_day_variance"]
        rk = row["rk_whole_day_variance"]
        gap = math.log(fixed / rk)
        items.append(
            {
                "session_date": row["session_date"],
                "abs_log_gap": abs(gap),
                "log_ratio_fixed_to_rk": gap,
                "fixed_to_rk_ratio": fixed / rk,
            }
        )
    return sorted(
        items,
        key=lambda item: item["abs_log_gap"],
        reverse=True,
    )[:10]


def _panel_medians(
    metrics: dict[str, dict[str, dict[str, float | int]]],
    symbols: tuple[str, ...],
) -> dict[str, dict[str, float]]:
    keys = (
        "geometric_bias_pct",
        "mean_abs_log_gap",
        "pearson_log",
        "spearman",
        "median_ratio",
    )
    return {
        f"{interval}m": {
            key: statistics.median(
                float(metrics[symbol][f"{interval}m"][key])
                for symbol in symbols
            )
            for key in keys
        }
        for interval in GRID_MINUTES
    }


def _decision(
    metrics: dict[str, dict[str, dict[str, float | int]]],
    panel: dict[str, dict[str, float]],
    symbols: tuple[str, ...],
) -> dict[str, Any]:
    best_bias = {
        symbol: min(
            (f"{interval}m" for interval in GRID_MINUTES),
            key=lambda grid: abs(
                float(metrics[symbol][grid]["geometric_bias_pct"])
            ),
        )
        for symbol in symbols
    }
    best_gap = min(
        panel,
        key=lambda grid: panel[grid]["mean_abs_log_gap"],
    )
    unanimous = len(set(best_bias.values())) == 1
    bias_winner = next(iter(best_bias.values())) if unanimous else None
    freeze = unanimous and bias_winner == best_gap
    return {
        "best_absolute_level_bias_by_symbol": best_bias,
        "best_panel_median_abs_log_gap": best_gap,
        "freeze_allowed": freeze,
        "canonical_sampling_candidate": (
            bias_winner if freeze else "INCONCLUSIVE"
        ),
        "forecast_score_used": False,
    }


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in row.items()
    }


def _self_check_math() -> None:
    assert math.isclose(_parzen_weight(0.25), 0.71875)
    assert math.isclose(_parzen_weight(0.5), 0.25)
    assert math.isclose(_parzen_weight(0.75), 0.03125)
    assert _jitter((0.0, 2.0, 4.0, 6.0, 8.0, 10.0), 2) == (
        1.0,
        4.0,
        6.0,
        9.0,
    )
    assert math.isclose(
        _noise_variance((0.0, 1.0, 2.0, 4.0, 6.0, 9.0), 2),
        6.75,
    )
    start = datetime(2026, 1, 1, tzinfo=timedelta(0))
    timestamps = (
        start,
        start + timedelta(seconds=1),
        start + timedelta(seconds=3),
        start + timedelta(seconds=4),
    )
    assert math.isclose(
        _sparse_rv(
            timestamps,
            (0.0, 1.0, 2.0, 4.0),
            2,
            1,
        ),
        5.5,
    )
    assert _bandwidth(1.0, 1.0, 32, 3.5134) == 29
    assert math.isclose(
        _parzen_rk(
            (0.0, 2.0, 4.0, 6.0, 8.0, 10.0),
            2,
            2,
        ),
        110.0 / 3.0,
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("task100_invalid_json")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
