import json
import math
from pathlib import Path
from typing import Any

import numpy as np

SYMBOLS = ("AAPL", "NVDA")
SESSION_DATE = "2026-09-24"
ELIGIBLE_CONDITIONS = frozenset(
    ("@", "A", "B", "D", "F", "K", "L", "O", "T", "X", "Y", "5", "6")
)
INELIGIBLE_CONDITIONS = frozenset(
    ("C", "G", "H", "I", "M", "N", "P", "Q", "R", "U", "V", "W", "Z", "4", "7", "9")
)
KNOWN_CONDITIONS = ELIGIBLE_CONDITIONS | INELIGIBLE_CONDITIONS

ENDPOINT_JITTER_M = 2
BANDWIDTH_CONSTANT = 3.5134
NOISE_TARGET_SECONDS = 120
SPARSE_INTERVAL_SECONDS = 1200
SPARSE_PHASE_SHIFT_SECONDS = 1
GROSS_MISMATCH_LOG_THRESHOLD = math.log(1.10)

INPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-104-input"
)
TASK100_ROOT = INPUT_ROOT / "task100"
TASK102_ROOT = INPUT_ROOT / "task102"
TASK103_ROOT = INPUT_ROOT / "task103"
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-104-us-trade-rk-granularity"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"


def main() -> None:
    _self_check_math()
    task100_daily = _load_json(TASK100_ROOT / "daily-values.json")
    task103 = _load_json(TASK103_ROOT / "summary.json")

    results = []
    for symbol in SYMBOLS:
        reference = _task100_row(task100_daily, symbol)
        eligible_timestamps_ns, eligible_prices = _eligible_trades(symbol)
        _cross_check_task103(
            task103,
            symbol,
            len(eligible_prices),
        )

        log_prices = np.log(np.asarray(eligible_prices, dtype=np.float64))
        timestamp_ns = np.asarray(eligible_timestamps_ns, dtype=np.int64)

        q = _select_q(timestamp_ns, NOISE_TARGET_SECONDS)
        noise = _noise_variance(log_prices, q)
        sparse = _sparse_rv(
            timestamp_ns,
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
        intraday_trade_rk = _parzen_rk(
            log_prices,
            bandwidth,
            ENDPOINT_JITTER_M,
        )
        overnight = float(reference["overnight_variance"])
        whole_day_trade_rk = intraday_trade_rk + overnight
        whole_day_1m_rk = float(reference["rk_whole_day_variance"])

        log_ratio_1m_to_trade = math.log(
            whole_day_1m_rk / whole_day_trade_rk
        )
        grid_context = {}
        for interval in (5, 10, 15):
            value = float(
                reference[f"{interval}m_whole_day_variance"]
            )
            grid_context[f"{interval}m"] = {
                "whole_day_variance": value,
                "fixed_to_trade_rk_ratio": (
                    value / whole_day_trade_rk
                ),
                "log_ratio_fixed_to_trade_rk": math.log(
                    value / whole_day_trade_rk
                ),
            }

        results.append(
            {
                "symbol": symbol,
                "eligible_trade_count": len(eligible_prices),
                "q": q,
                "noise_variance": noise,
                "sparse_realized_variance": sparse,
                "bandwidth": bandwidth,
                "intraday_trade_rk": intraday_trade_rk,
                "overnight_variance": overnight,
                "whole_day_trade_rk": whole_day_trade_rk,
                "whole_day_1m_rk": whole_day_1m_rk,
                "one_minute_to_trade_rk_ratio": (
                    whole_day_1m_rk / whole_day_trade_rk
                ),
                "log_ratio_1m_to_trade_rk": log_ratio_1m_to_trade,
                "abs_log_ratio_1m_to_trade_rk": abs(
                    log_ratio_1m_to_trade
                ),
                "within_10pct_log_boundary": abs(
                    log_ratio_1m_to_trade
                )
                <= GROSS_MISMATCH_LOG_THRESHOLD,
                "fixed_grid_context": grid_context,
            }
        )

    no_gross_mismatch = all(
        row["within_10pct_log_boundary"]
        for row in results
    )
    summary = {
        "artifact_version": "task-104-us-trade-rk-granularity-v1",
        "task": 104,
        "session_date": SESSION_DATE,
        "status": "accepted",
        "estimator": {
            "version": "us-rk-parzen-trades-diagnostic-v1",
            "kernel": "parzen",
            "endpoint_jitter_m": ENDPOINT_JITTER_M,
            "bandwidth_constant": BANDWIDTH_CONSTANT,
            "noise_target_seconds": NOISE_TARGET_SECONDS,
            "sparse_interval_seconds": SPARSE_INTERVAL_SECONDS,
            "sparse_phase_shift_seconds": SPARSE_PHASE_SHIFT_SECONDS,
            "price_input": "task-103-price-eligible-sip-trades",
        },
        "diagnostic_rule": {
            "threshold_abs_log_ratio": GROSS_MISMATCH_LOG_THRESHOLD,
            "equivalent_ratio_boundary": 1.10,
            "sampling_winner_rule": False,
        },
        "symbols": results,
        "ruling": (
            "NO_GROSS_SOURCE_GRANULARITY_MISMATCH"
            if no_gross_mismatch
            else "MATERIAL_SOURCE_GRANULARITY_MISMATCH"
        ),
        "provider_calls": 0,
        "sampling_frozen": False,
        "forecast_score_used": False,
        "self_check": "pass",
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _task100_row(
    payload: dict[str, Any],
    symbol: str,
) -> dict[str, Any]:
    daily = payload.get("daily_values")
    if not isinstance(daily, dict):
        raise RuntimeError("task104_invalid_task100_daily")
    rows = daily.get(symbol)
    if not isinstance(rows, list):
        raise RuntimeError(f"task104_missing_task100_symbol:{symbol}")
    for row in rows:
        if (
            isinstance(row, dict)
            and row.get("session_date") == SESSION_DATE
        ):
            return row
    raise RuntimeError(
        f"task104_missing_task100_session:{symbol}:{SESSION_DATE}"
    )


def _eligible_trades(
    symbol: str,
) -> tuple[list[int], list[float]]:
    paths = sorted(
        (TASK102_ROOT / "pages" / symbol).glob("page-*.json")
    )
    if not paths:
        raise RuntimeError(f"task104_missing_trade_pages:{symbol}")

    timestamps: list[int] = []
    prices: list[float] = []
    previous_ns: int | None = None

    for path in paths:
        payload = _load_json(path)
        if payload.get("symbol") != symbol:
            raise RuntimeError(f"task104_symbol_mismatch:{symbol}")
        trades = payload.get("trades")
        if not isinstance(trades, list):
            raise RuntimeError(f"task104_invalid_trades:{symbol}")

        for trade in trades:
            if not isinstance(trade, dict):
                raise RuntimeError("task104_invalid_trade")
            conditions = trade.get("c")
            if not isinstance(conditions, list) or not conditions:
                raise RuntimeError(f"task104_invalid_conditions:{symbol}")
            unknown = set(conditions) - KNOWN_CONDITIONS
            if unknown:
                raise RuntimeError(
                    f"task104_unknown_condition:{symbol}:{sorted(unknown)}"
                )
            if not all(
                condition in ELIGIBLE_CONDITIONS
                for condition in conditions
            ):
                continue

            timestamp_ns = _timestamp_to_ns(trade.get("t"))
            if previous_ns is not None and timestamp_ns <= previous_ns:
                raise RuntimeError(
                    f"task104_non_increasing_eligible_timestamp:{symbol}"
                )
            previous_ns = timestamp_ns

            price = trade.get("p")
            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or not math.isfinite(float(price))
                or float(price) <= 0.0
            ):
                raise RuntimeError(f"task104_invalid_price:{symbol}")

            timestamps.append(timestamp_ns)
            prices.append(float(price))

    if len(prices) < 10:
        raise RuntimeError(f"task104_insufficient_eligible_trades:{symbol}")
    return timestamps, prices


def _cross_check_task103(
    payload: dict[str, Any],
    symbol: str,
    eligible_count: int,
) -> None:
    rows = payload.get("symbols")
    if not isinstance(rows, list):
        raise RuntimeError("task104_invalid_task103")
    for row in rows:
        if isinstance(row, dict) and row.get("symbol") == symbol:
            if row.get("eligible_trade_count") != eligible_count:
                raise RuntimeError(
                    f"task104_task103_eligible_count_mismatch:{symbol}"
                )
            if row.get("ohlc_mismatch_count") != 0:
                raise RuntimeError(
                    f"task104_task103_not_accepted:{symbol}"
                )
            return
    raise RuntimeError(f"task104_missing_task103_symbol:{symbol}")


def _select_q(
    timestamps_ns: np.ndarray,
    target_spacing_seconds: int,
) -> int:
    elapsed_seconds = (
        int(timestamps_ns[-1]) - int(timestamps_ns[0])
    ) / 1_000_000_000.0
    if elapsed_seconds <= 0.0:
        raise RuntimeError("task104_invalid_elapsed")
    mean_gap = elapsed_seconds / (len(timestamps_ns) - 1)
    raw = target_spacing_seconds / mean_gap
    return max(
        1,
        min(math.floor(raw + 0.5), len(timestamps_ns) - 1),
    )


def _noise_variance(
    log_prices: np.ndarray,
    q: int,
) -> float:
    estimates: list[float] = []
    for offset in range(q):
        returns = np.diff(log_prices[offset::q])
        if returns.size == 0:
            continue
        nonzero = int(np.count_nonzero(returns))
        if nonzero == 0:
            estimates.append(0.0)
        else:
            estimates.append(
                float(np.dot(returns, returns))
                / (2.0 * nonzero)
            )
    if not estimates:
        raise RuntimeError("task104_no_noise_estimate")
    return math.fsum(estimates) / len(estimates)


def _sparse_rv(
    timestamps_ns: np.ndarray,
    log_prices: np.ndarray,
    interval_seconds: int,
    phase_shift_seconds: int,
) -> float:
    interval_ns = interval_seconds * 1_000_000_000
    start = int(timestamps_ns[0])
    end = int(timestamps_ns[-1])
    estimates: list[float] = []

    for offset_seconds in range(
        0,
        interval_seconds,
        phase_shift_seconds,
    ):
        first_grid = start + offset_seconds * 1_000_000_000
        if first_grid > end:
            break
        grid = np.arange(
            first_grid,
            end + 1,
            interval_ns,
            dtype=np.int64,
        )
        indices = (
            np.searchsorted(
                timestamps_ns,
                grid,
                side="right",
            )
            - 1
        )
        indices = indices[indices >= 0]
        if indices.size < 2:
            continue
        returns = np.diff(log_prices[indices])
        estimates.append(float(np.dot(returns, returns)))

    if not estimates:
        raise RuntimeError("task104_no_sparse_phase")
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
        raise RuntimeError("task104_invalid_sparse_rv")
    xi = math.sqrt(noise / sparse)
    raw = (
        constant
        * xi ** (4.0 / 5.0)
        * return_count ** (3.0 / 5.0)
    )
    return max(
        1,
        min(math.ceil(raw), return_count - 1),
    )


def _parzen_rk(
    log_prices: np.ndarray,
    bandwidth: int,
    m: int,
) -> float:
    if m != 2 or len(log_prices) < 4:
        raise RuntimeError("task104_invalid_jitter_input")
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
        if 0.0 <= x <= 0.5:
            weight = 1.0 - 6.0 * x * x + 6.0 * x * x * x
        elif x <= 1.0:
            weight = 2.0 * (1.0 - x) ** 3
        else:
            weight = 0.0
        result += (
            2.0
            * weight
            * float(np.dot(returns[lag:], returns[:-lag]))
        )

    if result < 0.0:
        if math.isclose(result, 0.0, abs_tol=1e-15):
            return 0.0
        raise RuntimeError("task104_negative_rk")
    return result


def _timestamp_to_ns(value: object) -> int:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError("task104_invalid_timestamp")
    body = value[:-1]
    if "." in body:
        base_text, fraction = body.split(".", 1)
    else:
        base_text, fraction = body, ""
    if len(fraction) > 9 or not fraction.isdigit():
        raise RuntimeError("task104_invalid_timestamp_fraction")
    from datetime import datetime, timezone

    base = datetime.fromisoformat(base_text).replace(
        tzinfo=timezone.utc
    )
    return (
        int(base.timestamp()) * 1_000_000_000
        + int(fraction.ljust(9, "0") or "0")
    )


def _self_check_math() -> None:
    def weight(x: float) -> float:
        if 0.0 <= x <= 0.5:
            return 1.0 - 6.0 * x * x + 6.0 * x * x * x
        if 0.5 < x <= 1.0:
            return 2.0 * (1.0 - x) ** 3
        return 0.0

    if not math.isclose(weight(0.25), 0.71875):
        raise RuntimeError("task104_parzen_self_check")
    if not math.isclose(weight(0.5), 0.25):
        raise RuntimeError("task104_parzen_self_check")
    if not math.isclose(weight(0.75), 0.03125):
        raise RuntimeError("task104_parzen_self_check")

    oracle = np.asarray(
        (0.0, 2.0, 4.0, 6.0, 8.0, 10.0),
        dtype=float,
    )
    if not math.isclose(
        _parzen_rk(oracle, 2, 2),
        110.0 / 3.0,
    ):
        raise RuntimeError("task104_rk_self_check")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"task104_invalid_json:{path}")
    return value


if __name__ == "__main__":
    main()
