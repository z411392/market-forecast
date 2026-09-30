import json
import math
import statistics
from datetime import date, datetime, time, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from scipy.stats import spearmanr

from libs.realized_variance.domain.services.build_default_realized_kernel_parameters import (
    build_default_realized_kernel_parameters,
)
from libs.realized_variance.domain.services.calculate_parzen_realized_kernel import (
    calculate_parzen_realized_kernel,
)
from libs.realized_variance.domain.services.calculate_realized_kernel_bandwidth import (
    calculate_realized_kernel_bandwidth,
)
from libs.realized_variance.domain.services.compose_noise_robust_daily_variance import (
    compose_noise_robust_daily_variance,
)
from libs.realized_variance.domain.services.estimate_noise_variance_from_subgrids import (
    estimate_noise_variance_from_subgrids,
)
from libs.realized_variance.domain.services.estimate_sparse_realized_variance import (
    estimate_sparse_realized_variance,
)
from libs.realized_variance.domain.services.select_noise_subgrid_stride import (
    select_noise_subgrid_stride,
)

MANIFEST = Path(
    "docs/research/provider-acceptance/task-90-s4h-empirical-input.json"
)
INPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-90-s4h-input"
)
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-90-s4h-empirical-rk-comparison"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"
LOCAL_TZ = ZoneInfo("Asia/Taipei")
GRID_MINUTES = (5, 10, 15)
METRIC_TOLERANCE = 1e-10
FORMULA_TOLERANCE = 1e-12


def main() -> None:
    manifest = _load_json(MANIFEST)
    evidence = _load_evidence(INPUT_ROOT)
    symbols = tuple(_require_str(value) for value in manifest["symbols"])
    sessions = _validate_coverage(evidence, symbols, manifest)
    audit_sessions = sessions[1:]
    params = build_default_realized_kernel_parameters()

    daily_values: dict[str, list[dict[str, Any]]] = {}
    metrics: dict[str, dict[str, dict[str, float | int]]] = {}
    formula_checks: list[dict[str, Any]] = []

    for symbol in symbols:
        rows: list[dict[str, Any]] = []
        previous_close = evidence[(symbol, sessions[0])]["closing_price"]

        for session_date in audit_sessions:
            day = evidence[(symbol, session_date)]
            result = _calculate_day(
                symbol=symbol,
                session_date=session_date,
                day=day,
                previous_closing_price=previous_close,
                params=params,
            )
            rows.append(result)
            previous_close = day["closing_price"]

            if session_date.isoformat() == manifest["formula_cross_check_session"]:
                formula_checks.append(
                    _cross_check_frozen_services(
                        symbol=symbol,
                        session_date=session_date,
                        day=day,
                        result=result,
                        params=params,
                    )
                )

        daily_values[symbol] = rows
        metrics[symbol] = {
            f"{interval}m": _summarize_grid(rows, interval)
            for interval in GRID_MINUTES
        }

    panel_medians = _panel_medians(metrics, symbols)
    level_ordering = {
        symbol: _level_bias_ordering(metrics[symbol])
        for symbol in symbols
    }
    expected_audit_count = _require_int(manifest["expected_audit_session_count"])
    final_required_count = _require_int(
        manifest["final_required_audit_session_count"]
    )

    summary: dict[str, Any] = {
        "artifact_version": manifest["output_version"],
        "task": 90,
        "status": (
            "final_gate_ready"
            if expected_audit_count == final_required_count
            else "interim_not_final"
        ),
        "estimator_version": params["estimator_version"],
        "audit_window": {
            "first": audit_sessions[0].isoformat(),
            "last": audit_sessions[-1].isoformat(),
            "audit_sessions_per_symbol": len(audit_sessions),
            "symbols": list(symbols),
        },
        "metrics": metrics,
        "panel_medians": panel_medians,
        "validation": {
            "formula_cross_checks": formula_checks,
            "reference_summary_match": None,
        },
        "interpretation": {
            "level_bias_ordering_by_symbol": level_ordering,
            "canonical_freeze_allowed": (
                len(audit_sessions) == final_required_count
            ),
            "final_required_audit_session_count": final_required_count,
        },
    }

    reference_path_raw = manifest.get("reference_summary")
    if reference_path_raw is not None:
        reference_path = Path(_require_str(reference_path_raw))
        reference = _load_json(reference_path)
        _assert_reference_metrics_match(summary, reference, symbols)
        summary["validation"]["reference_summary_match"] = {
            "path": str(reference_path),
            "tolerance": METRIC_TOLERANCE,
            "status": "pass",
        }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    DAILY_PATH.write_text(
        json.dumps(
            {
                "artifact_version": manifest["output_version"],
                "estimator_version": params["estimator_version"],
                "daily_values": daily_values,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def _load_evidence(root: Path) -> dict[tuple[str, date], dict[str, Any]]:
    evidence: dict[tuple[str, date], dict[str, Any]] = {}
    transaction_paths = sorted(root.glob("batch-*/cache/shioaji/*/transactions.json"))
    if not transaction_paths:
        raise RuntimeError("s4h_no_transaction_evidence")

    for transaction_path in transaction_paths:
        evidence_dir = transaction_path.parent
        receipt_path = evidence_dir / "receipt.json"
        if not receipt_path.is_file():
            raise RuntimeError("s4h_missing_receipt")

        transaction_bytes = transaction_path.read_bytes()
        transaction_payload = json.loads(transaction_bytes)
        receipt = _load_json(receipt_path)

        expected_hash = _require_str(receipt["transaction_sequence_sha256"])
        if sha256(transaction_bytes).hexdigest() != expected_hash:
            raise RuntimeError("s4h_transaction_hash_mismatch")
        if receipt["estimator_version"] != "tw-rk-parzen-trades-v1":
            raise RuntimeError("s4h_estimator_identity_mismatch")

        symbol = _require_str(transaction_payload["source_symbol"])
        session_date = date.fromisoformat(
            _require_str(transaction_payload["session_date"])
        )
        if receipt["source_symbol"] != symbol:
            raise RuntimeError("s4h_receipt_symbol_mismatch")
        if receipt["session_date"] != session_date.isoformat():
            raise RuntimeError("s4h_receipt_session_mismatch")

        transactions_raw = transaction_payload["transactions"]
        if not isinstance(transactions_raw, list) or len(transactions_raw) < 5:
            raise RuntimeError("s4h_invalid_transaction_sequence")

        timestamps: list[datetime] = []
        prices: list[float] = []
        previous: datetime | None = None
        for transaction in transactions_raw:
            if not isinstance(transaction, dict):
                raise RuntimeError("s4h_invalid_transaction")
            observed_at = datetime.fromisoformat(
                _require_str(transaction["observed_at_utc"])
            )
            if observed_at.tzinfo is None or observed_at.utcoffset() != timezone.utc.utcoffset(
                observed_at
            ):
                raise RuntimeError("s4h_transaction_not_utc")
            if previous is not None and observed_at < previous:
                raise RuntimeError("s4h_decreasing_transaction_time")
            previous = observed_at

            price = float(transaction["price"])
            if not math.isfinite(price) or price <= 0.0:
                raise RuntimeError("s4h_invalid_transaction_price")
            timestamps.append(observed_at)
            prices.append(price)

        opening_price = float(receipt["opening_price"])
        closing_price = float(receipt["closing_auction_price"])
        if not math.isclose(prices[0], opening_price, rel_tol=1e-12, abs_tol=1e-15):
            raise RuntimeError("s4h_opening_price_mismatch")
        if not math.isclose(prices[-1], closing_price, rel_tol=1e-12, abs_tol=1e-15):
            raise RuntimeError("s4h_closing_price_mismatch")

        key = (symbol, session_date)
        if key in evidence:
            raise RuntimeError("s4h_duplicate_symbol_session")
        evidence[key] = {
            "security": transaction_payload["security"],
            "timestamps": tuple(timestamps),
            "prices": tuple(prices),
            "opening_price": opening_price,
            "closing_price": closing_price,
            "request_sha256": _require_str(receipt["request_sha256"]),
        }

    return evidence


def _validate_coverage(
    evidence: dict[tuple[str, date], dict[str, Any]],
    symbols: tuple[str, ...],
    manifest: dict[str, Any],
) -> tuple[date, ...]:
    by_symbol = {
        symbol: tuple(sorted(session for item_symbol, session in evidence if item_symbol == symbol))
        for symbol in symbols
    }
    first_symbol = symbols[0]
    sessions = by_symbol[first_symbol]
    for symbol in symbols[1:]:
        if by_symbol[symbol] != sessions:
            raise RuntimeError("s4h_cross_symbol_session_mismatch")

    expected_count = _require_int(manifest["expected_session_count"])
    if len(sessions) != expected_count:
        raise RuntimeError("s4h_unexpected_session_count")
    if sessions[0].isoformat() != manifest["first_session_date"]:
        raise RuntimeError("s4h_unexpected_first_session")
    if sessions[-1].isoformat() != manifest["last_session_date"]:
        raise RuntimeError("s4h_unexpected_last_session")
    return sessions


def _calculate_day(
    *,
    symbol: str,
    session_date: date,
    day: dict[str, Any],
    previous_closing_price: float,
    params: dict[str, Any],
) -> dict[str, Any]:
    timestamps = day["timestamps"]
    prices = day["prices"]
    timestamp_us = np.fromiter(
        (_datetime_to_microseconds(value) for value in timestamps),
        dtype=np.int64,
    )
    price_array = np.asarray(prices, dtype=np.float64)
    log_prices = np.log(price_array)

    q = _optimized_noise_subgrid_stride(
        timestamp_us,
        params["noise_target_spacing_seconds"],
    )
    noise_variance = _optimized_noise_variance(log_prices, q)
    sparse_rv = _optimized_sparse_rv(
        timestamp_us,
        log_prices,
        params["sparse_interval_seconds"],
        params["sparse_phase_shift_seconds"],
    )
    return_count = len(prices) - 3
    bandwidth = calculate_realized_kernel_bandwidth(
        noise_variance=noise_variance,
        sparse_realized_variance=sparse_rv,
        return_count=return_count,
        bandwidth_constant=params["bandwidth_constant"],
    )
    intraday_rk = _optimized_parzen_rk(
        log_prices,
        bandwidth,
        params["endpoint_jitter_m"],
    )

    daily = compose_noise_robust_daily_variance(
        security=day["security"],
        session_date=session_date,
        price_basis="as_printed",
        previous_closing_price=previous_closing_price,
        current_opening_price=day["opening_price"],
        intraday_realized_kernel=intraday_rk,
        tick_count=len(prices),
        return_count=return_count,
        bandwidth=bandwidth,
        noise_variance=noise_variance,
        sparse_realized_variance=sparse_rv,
    )

    fixed_grid = {
        f"{interval}m": _fixed_grid_whole_day_variance(
            session_date=session_date,
            timestamp_us=timestamp_us,
            prices=price_array,
            interval_minutes=interval,
            overnight_variance=daily["overnight_variance"],
        )
        for interval in GRID_MINUTES
    }

    if daily["whole_day_variance"] <= 0.0:
        raise RuntimeError("s4h_non_positive_rk_whole_day_variance")
    if any(value <= 0.0 for value in fixed_grid.values()):
        raise RuntimeError("s4h_non_positive_fixed_grid_whole_day_variance")

    return {
        "session_date": session_date.isoformat(),
        "rk_whole_day_variance": daily["whole_day_variance"],
        "intraday_realized_kernel": intraday_rk,
        "overnight_variance": daily["overnight_variance"],
        "tick_count": len(prices),
        "q": q,
        "noise_variance": noise_variance,
        "sparse_realized_variance": sparse_rv,
        "bandwidth": bandwidth,
        **{
            f"whole_day_variance_{interval}m": fixed_grid[f"{interval}m"]
            for interval in GRID_MINUTES
        },
    }


def _cross_check_frozen_services(
    *,
    symbol: str,
    session_date: date,
    day: dict[str, Any],
    result: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    timestamps = day["timestamps"]
    log_prices = tuple(math.log(value) for value in day["prices"])

    q = select_noise_subgrid_stride(
        timestamps,
        params["noise_target_spacing_seconds"],
    )
    noise_variance = estimate_noise_variance_from_subgrids(log_prices, q)
    sparse_rv = estimate_sparse_realized_variance(
        timestamps=timestamps,
        log_prices=log_prices,
        interval_seconds=params["sparse_interval_seconds"],
        phase_shift_seconds=params["sparse_phase_shift_seconds"],
    )
    bandwidth = calculate_realized_kernel_bandwidth(
        noise_variance=noise_variance,
        sparse_realized_variance=sparse_rv,
        return_count=len(log_prices) - 3,
        bandwidth_constant=params["bandwidth_constant"],
    )
    intraday_rk = calculate_parzen_realized_kernel(
        log_prices=log_prices,
        bandwidth=bandwidth,
        endpoint_jitter_m=params["endpoint_jitter_m"],
    )

    checks = {
        "q_equal": q == result["q"],
        "noise_variance_abs_diff": abs(
            noise_variance - result["noise_variance"]
        ),
        "sparse_rv_abs_diff": abs(
            sparse_rv - result["sparse_realized_variance"]
        ),
        "bandwidth_equal": bandwidth == result["bandwidth"],
        "rk_abs_diff": abs(intraday_rk - result["intraday_realized_kernel"]),
    }
    if not checks["q_equal"] or not checks["bandwidth_equal"]:
        raise RuntimeError("s4h_formula_integer_cross_check_failed")
    for key in ("noise_variance_abs_diff", "sparse_rv_abs_diff", "rk_abs_diff"):
        if checks[key] > FORMULA_TOLERANCE:
            raise RuntimeError(f"s4h_formula_cross_check_failed:{key}")

    return {
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        **checks,
    }


def _optimized_noise_subgrid_stride(
    timestamp_us: np.ndarray,
    target_spacing_seconds: int,
) -> int:
    elapsed_seconds = (
        int(timestamp_us[-1]) - int(timestamp_us[0])
    ) / 1_000_000.0
    if elapsed_seconds <= 0.0:
        raise RuntimeError("s4h_zero_elapsed_tick_session")
    average_gap = elapsed_seconds / (len(timestamp_us) - 1)
    raw_stride = target_spacing_seconds / average_gap
    return max(1, min(math.floor(raw_stride + 0.5), len(timestamp_us) - 1))


def _optimized_noise_variance(log_prices: np.ndarray, q: int) -> float:
    estimates: list[float] = []
    for offset in range(q):
        returns = np.diff(log_prices[offset::q])
        if returns.size == 0:
            continue
        nonzero_count = int(np.count_nonzero(returns))
        if nonzero_count == 0:
            estimates.append(0.0)
        else:
            estimates.append(
                float(np.dot(returns, returns)) / (2.0 * nonzero_count)
            )
    if not estimates:
        raise RuntimeError("s4h_no_noise_subgrid")
    return float(statistics.fmean(estimates))


def _optimized_sparse_rv(
    timestamp_us: np.ndarray,
    log_prices: np.ndarray,
    interval_seconds: int,
    phase_shift_seconds: int,
) -> float:
    interval_us = interval_seconds * 1_000_000
    start = int(timestamp_us[0])
    end = int(timestamp_us[-1])
    estimates: list[float] = []

    for offset_seconds in range(
        0,
        interval_seconds,
        phase_shift_seconds,
    ):
        first_grid = start + offset_seconds * 1_000_000
        if first_grid > end:
            break
        grid = np.arange(
            first_grid,
            end + 1,
            interval_us,
            dtype=np.int64,
        )
        indices = np.searchsorted(timestamp_us, grid, side="right") - 1
        indices = indices[indices >= 0]
        if indices.size < 2:
            continue
        returns = np.diff(log_prices[indices])
        estimates.append(float(np.dot(returns, returns)))

    if not estimates:
        raise RuntimeError("s4h_no_sparse_rv_phase")
    return float(statistics.fmean(estimates))


def _optimized_parzen_rk(
    log_prices: np.ndarray,
    bandwidth: int,
    endpoint_jitter_m: int,
) -> float:
    m = endpoint_jitter_m
    jittered = np.concatenate(
        (
            np.asarray([float(np.mean(log_prices[:m]))]),
            log_prices[m:-m],
            np.asarray([float(np.mean(log_prices[-m:]))]),
        )
    )
    returns = np.diff(jittered)
    result = float(np.dot(returns, returns))
    max_lag = min(bandwidth, len(returns) - 1)

    for lag in range(1, max_lag + 1):
        x = lag / (bandwidth + 1.0)
        if x <= 0.5:
            weight = 1.0 - 6.0 * x * x + 6.0 * x * x * x
        else:
            weight = 2.0 * (1.0 - x) ** 3
        result += 2.0 * weight * float(
            np.dot(returns[lag:], returns[:-lag])
        )

    if result < 0.0:
        if math.isclose(result, 0.0, rel_tol=0.0, abs_tol=1e-15):
            return 0.0
        raise RuntimeError("s4h_negative_realized_kernel")
    return result


def _fixed_grid_whole_day_variance(
    *,
    session_date: date,
    timestamp_us: np.ndarray,
    prices: np.ndarray,
    interval_minutes: int,
    overnight_variance: float,
) -> float:
    session_start = datetime.combine(
        session_date,
        time(9, 0),
        tzinfo=LOCAL_TZ,
    ).astimezone(timezone.utc)
    closing_at = datetime.combine(
        session_date,
        time(13, 30),
        tzinfo=LOCAL_TZ,
    ).astimezone(timezone.utc)

    boundary_us = np.arange(
        _datetime_to_microseconds(session_start)
        + interval_minutes * 60 * 1_000_000,
        _datetime_to_microseconds(closing_at),
        interval_minutes * 60 * 1_000_000,
        dtype=np.int64,
    )
    indices = np.searchsorted(timestamp_us, boundary_us, side="left") - 1
    if np.any(indices < 0):
        raise RuntimeError("s4h_missing_previous_tick_for_fixed_grid")

    sampled_prices = np.concatenate(
        (
            np.asarray([prices[0]]),
            prices[indices],
            np.asarray([prices[-1]]),
        )
    )
    returns = np.diff(np.log(sampled_prices))
    intraday_variance = float(np.dot(returns, returns))
    return intraday_variance + overnight_variance


def _summarize_grid(
    rows: list[dict[str, Any]],
    interval_minutes: int,
) -> dict[str, float | int]:
    grid_key = f"whole_day_variance_{interval_minutes}m"
    grid = np.asarray([row[grid_key] for row in rows], dtype=np.float64)
    rk = np.asarray(
        [row["rk_whole_day_variance"] for row in rows],
        dtype=np.float64,
    )
    log_grid = np.log(grid)
    log_rk = np.log(rk)
    log_gap = log_grid - log_rk

    spearman_value = spearmanr(grid, rk).statistic
    if not math.isfinite(float(spearman_value)):
        raise RuntimeError("s4h_non_finite_spearman")

    return {
        "n": len(rows),
        "geometric_bias_pct": (
            math.exp(float(np.mean(log_gap))) - 1.0
        )
        * 100.0,
        "mean_abs_log_gap": float(np.mean(np.abs(log_gap))),
        "pearson_log": float(np.corrcoef(log_grid, log_rk)[0, 1]),
        "spearman": float(spearman_value),
        "median_ratio": float(np.median(grid / rk)),
    }


def _panel_medians(
    metrics: dict[str, dict[str, dict[str, float | int]]],
    symbols: tuple[str, ...],
) -> dict[str, dict[str, float]]:
    metric_names = (
        "geometric_bias_pct",
        "mean_abs_log_gap",
        "pearson_log",
        "spearman",
        "median_ratio",
    )
    return {
        f"{interval}m": {
            metric_name: statistics.median(
                float(metrics[symbol][f"{interval}m"][metric_name])
                for symbol in symbols
            )
            for metric_name in metric_names
        }
        for interval in GRID_MINUTES
    }


def _level_bias_ordering(
    symbol_metrics: dict[str, dict[str, float | int]],
) -> list[str]:
    return sorted(
        symbol_metrics,
        key=lambda grid: abs(
            float(symbol_metrics[grid]["geometric_bias_pct"])
        ),
    )


def _assert_reference_metrics_match(
    actual: dict[str, Any],
    reference: dict[str, Any],
    symbols: tuple[str, ...],
) -> None:
    for symbol in symbols:
        for interval in GRID_MINUTES:
            grid = f"{interval}m"
            for metric in (
                "geometric_bias_pct",
                "mean_abs_log_gap",
                "pearson_log",
                "spearman",
                "median_ratio",
            ):
                difference = abs(
                    float(actual["metrics"][symbol][grid][metric])
                    - float(reference["metrics"][symbol][grid][metric])
                )
                if difference > METRIC_TOLERANCE:
                    raise RuntimeError(
                        "s4h_reference_metric_mismatch:"
                        f"{symbol}:{grid}:{metric}:{difference}"
                    )


def _datetime_to_microseconds(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise RuntimeError("s4h_datetime_not_utc")
    return int(value.timestamp()) * 1_000_000 + value.microsecond


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("s4h_invalid_json_object")
    return value


def _require_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("s4h_invalid_string")
    return value


def _require_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("s4h_invalid_integer")
    return value


if __name__ == "__main__":
    main()
