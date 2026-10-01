import gzip
import json
import math
import re
import statistics
from bisect import bisect_right
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

PLAN_PATH = Path(
    "docs/research/provider-acceptance/task-105-us-transaction-rk-plan.json"
)
INPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-105-final-input"
)
TASK97_ROOT = INPUT_ROOT / "task97"
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-105-us-transaction-rk-final"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"

GRID_MINUTES = (5, 10, 15)
ESTIMATOR_VERSION = "us-rk-parzen-trades-v1"
_TIMESTAMP_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(\d{1,9}))?Z$"
)


def main() -> None:
    _self_check_math()
    plan = _load_json(PLAN_PATH)
    _validate_plan(plan)
    fixed = _load_task97_fixed_grid()
    evidence = _load_eligible_trade_sequences(plan)

    symbols = tuple(plan["symbols"])
    dates = tuple(plan["sample"]["dates"])
    estimator = plan["estimator"]

    metrics: dict[str, dict[str, dict[str, float | int]]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    daily_output: dict[str, list[dict[str, Any]]] = {}

    for symbol in symbols:
        rows: list[dict[str, Any]] = []
        bandwidths: list[int] = []
        q_values: list[int] = []
        eligible_counts: list[int] = []
        noise_values: list[float] = []
        sparse_values: list[float] = []

        for session_date in dates:
            timestamps_ns, prices = evidence[(symbol, session_date)]
            fixed_row = fixed[(symbol, session_date)]

            log_prices = tuple(math.log(value) for value in prices)
            q = _select_q(
                timestamps_ns,
                int(estimator["noise_target_spacing_seconds"]),
            )
            noise = _noise_variance(log_prices, q)
            sparse = _sparse_rv(
                timestamps_ns,
                log_prices,
                int(estimator["sparse_interval_seconds"]),
                int(estimator["sparse_phase_shift_seconds"]),
            )
            return_count = len(log_prices) - 3
            bandwidth = _bandwidth(
                noise,
                sparse,
                return_count,
                float(estimator["bandwidth_constant"]),
            )
            intraday_rk = _parzen_rk(
                log_prices,
                bandwidth,
                int(estimator["endpoint_jitter_m"]),
            )
            overnight_variance = float(fixed_row["overnight_variance"])
            whole_day_rk = intraday_rk + overnight_variance
            if not math.isfinite(whole_day_rk) or whole_day_rk <= 0.0:
                raise RuntimeError(
                    f"task105_nonpositive_rk:{symbol}:{session_date}"
                )

            row: dict[str, Any] = {
                "session_date": session_date,
                "eligible_trade_count": len(prices),
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
            eligible_counts.append(len(prices))
            noise_values.append(noise)
            sparse_values.append(sparse)

        metrics[symbol] = {
            f"{interval}m": _summarize_grid(rows, interval)
            for interval in GRID_MINUTES
        }
        diagnostics[symbol] = {
            "eligible_trade_count_min": min(eligible_counts),
            "eligible_trade_count_median": statistics.median(
                eligible_counts
            ),
            "eligible_trade_count_max": max(eligible_counts),
            "bandwidth_min": min(bandwidths),
            "bandwidth_median": statistics.median(bandwidths),
            "bandwidth_max": max(bandwidths),
            "q_min": min(q_values),
            "q_median": statistics.median(q_values),
            "q_max": max(q_values),
            "noise_variance_median": statistics.median(noise_values),
            "sparse_realized_variance_median": statistics.median(
                sparse_values
            ),
            "top_abs_log_gap_sessions": {
                f"{interval}m": _top_gaps(rows, interval)
                for interval in GRID_MINUTES
            },
        }
        daily_output[symbol] = rows

    panel = _panel_medians(metrics, symbols)
    decision = _decision(metrics, symbols)
    summary = {
        "artifact_version": "task-105-us-transaction-rk-final-v1",
        "task": 105,
        "parent_task": 12,
        "status": "accepted",
        "estimator": estimator,
        "sample": {
            "session_count": len(dates),
            "dates": list(dates),
            "selection_formula": plan["sample"]["formula"],
            "selection_uses_outcomes": False,
        },
        "metrics": metrics,
        "panel_medians": panel,
        "diagnostics": diagnostics,
        "decision": decision,
        "forecast_score_used": False,
        "provider_calls": 0,
        "self_check": "pass",
    }
    _write_json(SUMMARY_PATH, summary)
    _write_json(
        DAILY_PATH,
        {
            "artifact_version": "task-105-us-transaction-rk-daily-v1",
            "estimator_version": ESTIMATOR_VERSION,
            "daily_values": daily_output,
        },
    )


def _load_eligible_trade_sequences(
    plan: dict[str, Any],
) -> dict[tuple[str, str], tuple[tuple[int, ...], tuple[float, ...]]]:
    result: dict[
        tuple[str, str],
        tuple[tuple[int, ...], tuple[float, ...]],
    ] = {}
    for batch in plan["batches"]:
        batch_number = int(batch["batch"])
        batch_root = INPUT_ROOT / f"batch-{batch_number}"
        for session_date in batch["dates"]:
            for symbol in plan["symbols"]:
                root = (
                    batch_root
                    / "sessions"
                    / session_date
                    / symbol
                )
                sequence_path = root / "eligible-trades.jsonl.gz"
                summary_path = root / "session-summary.json"
                if not sequence_path.is_file() or not summary_path.is_file():
                    raise RuntimeError(
                        f"task105_missing_session_evidence:"
                        f"{batch_number}:{session_date}:{symbol}"
                    )
                session_summary = _load_json(summary_path)
                sequence_bytes = sequence_path.read_bytes()
                expected_sha = session_summary[
                    "eligible_sequence_sha256"
                ]
                import hashlib

                if hashlib.sha256(sequence_bytes).hexdigest() != expected_sha:
                    raise RuntimeError(
                        f"task105_eligible_sequence_hash_mismatch:"
                        f"{session_date}:{symbol}"
                    )

                timestamps: list[int] = []
                prices: list[float] = []
                previous_ns: int | None = None
                with gzip.open(
                    sequence_path,
                    "rt",
                    encoding="utf-8",
                ) as source:
                    for line in source:
                        payload = json.loads(line)
                        if not isinstance(payload, dict):
                            raise RuntimeError(
                                "task105_invalid_eligible_record"
                            )
                        timestamp_ns = _timestamp_to_ns(
                            payload.get("t")
                        )
                        price = _positive_price(payload.get("p"))
                        if (
                            previous_ns is not None
                            and timestamp_ns < previous_ns
                        ):
                            raise RuntimeError(
                                "task105_decreasing_eligible_timestamp"
                            )
                        previous_ns = timestamp_ns
                        timestamps.append(timestamp_ns)
                        prices.append(price)

                expected_count = int(
                    session_summary["eligible_trade_count"]
                )
                if len(prices) != expected_count:
                    raise RuntimeError(
                        f"task105_eligible_count_mismatch:"
                        f"{session_date}:{symbol}"
                    )
                if len(prices) < 5:
                    raise RuntimeError(
                        f"task105_insufficient_eligible_trades:"
                        f"{session_date}:{symbol}"
                    )
                key = (symbol, session_date)
                if key in result:
                    raise RuntimeError("task105_duplicate_session_evidence")
                result[key] = (tuple(timestamps), tuple(prices))

    expected = len(plan["sample"]["dates"]) * len(plan["symbols"])
    if len(result) != expected:
        raise RuntimeError(
            f"task105_unexpected_session_evidence_count:{len(result)}"
        )
    return result


def _load_task97_fixed_grid() -> dict[tuple[str, str], dict[str, Any]]:
    candidates = list(TASK97_ROOT.rglob("daily-values.json"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"task105_task97_daily_values_identity:{len(candidates)}"
        )
    payload = _load_json(candidates[0])
    daily_values = payload.get("daily_values")
    if not isinstance(daily_values, dict):
        raise RuntimeError("task105_invalid_task97_daily_values")

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for symbol in ("AAPL", "NVDA"):
        rows = daily_values.get(symbol)
        if not isinstance(rows, list):
            raise RuntimeError(
                f"task105_missing_task97_symbol:{symbol}"
            )
        for row in rows:
            if not isinstance(row, dict):
                raise RuntimeError("task105_invalid_task97_row")
            session_date = row.get("session_date")
            if not isinstance(session_date, str):
                raise RuntimeError("task105_invalid_task97_session")
            result[(symbol, session_date)] = row
    return result


def _validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("task") != 105:
        raise RuntimeError("task105_wrong_plan_task")
    if plan.get("symbols") != ["AAPL", "NVDA"]:
        raise RuntimeError("task105_wrong_symbols")
    dates = plan["sample"]["dates"]
    if not isinstance(dates, list) or len(dates) != 24:
        raise RuntimeError("task105_wrong_sample_count")
    estimator = plan.get("estimator")
    if not isinstance(estimator, dict):
        raise RuntimeError("task105_missing_estimator")
    expected = {
        "identity": ESTIMATOR_VERSION,
        "endpoint_jitter_m": 2,
        "bandwidth_constant": 3.5134,
        "noise_target_spacing_seconds": 120,
        "sparse_interval_seconds": 1200,
        "sparse_phase_shift_seconds": 1,
        "eligibility_reference": (
            "task-103-alpaca-trade-price-eligibility-reference-v1"
        ),
    }
    if estimator != expected:
        raise RuntimeError("task105_estimator_identity_mismatch")


def _select_q(
    timestamps_ns: tuple[int, ...],
    target_spacing_seconds: int,
) -> int:
    elapsed_seconds = (
        timestamps_ns[-1] - timestamps_ns[0]
    ) / 1_000_000_000.0
    if not math.isfinite(elapsed_seconds) or elapsed_seconds <= 0.0:
        raise RuntimeError("task105_invalid_elapsed")
    mean_gap = elapsed_seconds / (len(timestamps_ns) - 1)
    raw = target_spacing_seconds / mean_gap
    return max(
        1,
        min(
            math.floor(raw + 0.5),
            len(timestamps_ns) - 1,
        ),
    )


def _noise_variance(
    log_prices: tuple[float, ...],
    q: int,
) -> float:
    estimates: list[float] = []
    for offset in range(q):
        subgrid = log_prices[offset::q]
        if len(subgrid) < 2:
            continue
        returns = tuple(
            current - previous
            for previous, current in zip(
                subgrid,
                subgrid[1:],
            )
        )
        nonzero_count = sum(value != 0.0 for value in returns)
        if nonzero_count == 0:
            estimates.append(0.0)
        else:
            rv = math.fsum(value * value for value in returns)
            estimates.append(rv / (2.0 * nonzero_count))
    if not estimates:
        raise RuntimeError("task105_no_noise_estimate")
    return math.fsum(estimates) / len(estimates)


def _sparse_rv(
    timestamps_ns: tuple[int, ...],
    log_prices: tuple[float, ...],
    interval_seconds: int,
    phase_shift_seconds: int,
) -> float:
    estimates: list[float] = []
    start = timestamps_ns[0]
    end = timestamps_ns[-1]
    interval_ns = interval_seconds * 1_000_000_000

    for offset_seconds in range(
        0,
        interval_seconds,
        phase_shift_seconds,
    ):
        grid_ns = start + offset_seconds * 1_000_000_000
        synchronized: list[float] = []
        while grid_ns <= end:
            index = bisect_right(timestamps_ns, grid_ns) - 1
            if index >= 0:
                synchronized.append(log_prices[index])
            grid_ns += interval_ns
        if len(synchronized) < 2:
            continue
        returns = tuple(
            current - previous
            for previous, current in zip(
                synchronized,
                synchronized[1:],
            )
        )
        estimates.append(
            math.fsum(value * value for value in returns)
        )
    if not estimates:
        raise RuntimeError("task105_no_sparse_phase")
    return math.fsum(estimates) / len(estimates)


def _bandwidth(
    noise: float,
    sparse: float,
    return_count: int,
    constant: float,
) -> int:
    if return_count < 2:
        raise RuntimeError("task105_insufficient_returns")
    if noise == 0.0:
        return 1
    if sparse <= 0.0:
        raise RuntimeError("task105_invalid_sparse_rv")
    xi = math.sqrt(noise / sparse)
    raw = (
        constant
        * xi ** (4.0 / 5.0)
        * return_count ** (3.0 / 5.0)
    )
    if not math.isfinite(raw):
        return return_count - 1
    return max(
        1,
        min(math.ceil(raw), return_count - 1),
    )


def _jitter(
    log_prices: tuple[float, ...],
    m: int,
) -> tuple[float, ...]:
    if m != 2 or len(log_prices) < 4:
        raise RuntimeError("task105_invalid_jitter_input")
    first = math.fsum(log_prices[:m]) / m
    last = math.fsum(log_prices[-m:]) / m
    return (first, *log_prices[m:-m], last)


def _parzen_weight(x: float) -> float:
    if 0.0 <= x <= 0.5:
        return 1.0 - 6.0 * x * x + 6.0 * x * x * x
    if 0.5 < x <= 1.0:
        return 2.0 * (1.0 - x) ** 3
    return 0.0


def _autocovariance(
    returns: tuple[float, ...],
    lag: int,
) -> float:
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
        for previous, current in zip(
            jittered,
            jittered[1:],
        )
    )
    result = _autocovariance(returns, 0)
    result += math.fsum(
        2.0
        * _parzen_weight(lag / (bandwidth + 1.0))
        * _autocovariance(returns, lag)
        for lag in range(
            1,
            min(bandwidth, len(returns) - 1) + 1,
        )
    )
    if result < 0.0:
        if math.isclose(
            result,
            0.0,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            return 0.0
        raise RuntimeError("task105_negative_rk")
    return result


def _summarize_grid(
    rows: list[dict[str, Any]],
    interval: int,
) -> dict[str, float | int]:
    fixed = np.asarray(
        [
            row[f"{interval}m_whole_day_variance"]
            for row in rows
        ],
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
    if not math.isfinite(spearman):
        raise RuntimeError("task105_nonfinite_spearman")
    pearson = float(np.corrcoef(log_fixed, log_rk)[0, 1])
    if not math.isfinite(pearson):
        raise RuntimeError("task105_nonfinite_pearson")
    return {
        "n": len(rows),
        "geometric_bias_pct": (
            math.exp(float(np.mean(gap))) - 1.0
        )
        * 100.0,
        "mean_abs_log_gap": float(
            np.mean(np.abs(gap))
        ),
        "pearson_log": pearson,
        "spearman": spearman,
        "median_ratio": float(
            np.median(fixed / rk)
        ),
    }


def _top_gaps(
    rows: list[dict[str, Any]],
    interval: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
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
                float(
                    metrics[symbol][f"{interval}m"][key]
                )
                for symbol in symbols
            )
            for key in keys
        }
        for interval in GRID_MINUTES
    }


def _decision(
    metrics: dict[str, dict[str, dict[str, float | int]]],
    symbols: tuple[str, ...],
) -> dict[str, Any]:
    winners = {
        symbol: min(
            (f"{interval}m" for interval in GRID_MINUTES),
            key=lambda grid: abs(
                float(
                    metrics[symbol][grid][
                        "geometric_bias_pct"
                    ]
                )
            ),
        )
        for symbol in symbols
    }
    unanimous = len(set(winners.values())) == 1
    candidate = (
        next(iter(winners.values()))
        if unanimous
        else "INCONCLUSIVE"
    )
    return {
        "best_absolute_level_bias_by_symbol": winners,
        "cross_symbol_unanimity": unanimous,
        "canonical_sampling_candidate": candidate,
        "selection_metric": "absolute_geometric_level_bias",
        "mean_abs_log_gap_is_diagnostic_only": True,
        "correlation_is_diagnostic_only": True,
        "forecast_score_used": False,
    }


def _timestamp_to_ns(value: object) -> int:
    if not isinstance(value, str):
        raise RuntimeError("task105_invalid_timestamp")
    match = _TIMESTAMP_RE.fullmatch(value)
    if match is None:
        raise RuntimeError(f"task105_invalid_timestamp:{value}")
    base_text, fraction = match.groups()
    import datetime as dt

    base = dt.datetime.fromisoformat(
        base_text
    ).replace(tzinfo=dt.timezone.utc)
    fraction_ns = int((fraction or "").ljust(9, "0"))
    return int(base.timestamp()) * 1_000_000_000 + fraction_ns


def _positive_price(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise RuntimeError("task105_invalid_price")
    return float(value)


def _self_check_math() -> None:
    assert math.isclose(_parzen_weight(0.25), 0.71875)
    assert math.isclose(_parzen_weight(0.5), 0.25)
    assert math.isclose(_parzen_weight(0.75), 0.03125)
    assert _jitter(
        (0.0, 2.0, 4.0, 6.0, 8.0, 10.0),
        2,
    ) == (1.0, 4.0, 6.0, 9.0)
    assert math.isclose(
        _noise_variance(
            (0.0, 1.0, 2.0, 4.0, 6.0, 9.0),
            2,
        ),
        6.75,
    )
    timestamps = (
        0,
        1_000_000_000,
        3_000_000_000,
        4_000_000_000,
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
        raise RuntimeError(f"task105_invalid_json:{path}")
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
