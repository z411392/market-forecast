import json
import math
import statistics
from hashlib import sha256
from pathlib import Path
from typing import Any

from libs.market_data.services.decode_alpaca_stock_bars import (
    decode_alpaca_stock_bars,
)
from libs.realized_variance.domain.services.aggregate_minute_bars import (
    aggregate_minute_bars,
)

SYMBOLS = ("AAPL", "NVDA")
CANDIDATE_INTERVALS = (5, 10, 15)
TASK97_ROOT = Path(
    "artifacts/private/provider-captures/task-106-replication-input/task97"
)
TASK106_ROOT = Path(
    "artifacts/private/provider-captures/task-106-replication-input/task106"
)
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-106-us-bandi-russell-replication"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"


def main() -> None:
    _cross_check_primary_formula()

    evidence = _load_evidence(TASK97_ROOT)
    sessions_by_symbol = {
        symbol: tuple(
            sorted(
                session
                for item_symbol, session in evidence
                if item_symbol == symbol
            )
        )
        for symbol in SYMBOLS
    }
    sessions = sessions_by_symbol[SYMBOLS[0]]
    if len(sessions) != 253:
        raise RuntimeError(
            f"task106r_unexpected_session_count:{len(sessions)}"
        )
    if sessions[0] != "2025-09-23":
        raise RuntimeError(
            f"task106r_unexpected_prior:{sessions[0]}"
        )
    if sessions[1] != "2025-09-24":
        raise RuntimeError(
            f"task106r_unexpected_first:{sessions[1]}"
        )
    if sessions[-1] != "2026-09-24":
        raise RuntimeError(
            f"task106r_unexpected_last:{sessions[-1]}"
        )
    if any(
        sessions_by_symbol[symbol] != sessions
        for symbol in SYMBOLS[1:]
    ):
        raise RuntimeError("task106r_cross_symbol_session_mismatch")

    daily: dict[str, list[dict[str, Any]]] = {
        symbol: [] for symbol in SYMBOLS
    }
    for symbol in SYMBOLS:
        for session in sessions[1:]:
            bars, session_start = evidence[(symbol, session)]
            daily[symbol].append(
                _calculate_session(
                    symbol=symbol,
                    session=session,
                    bars=bars,
                    session_start=session_start,
                )
            )

    results = [
        _summarize_symbol(symbol, daily[symbol])
        for symbol in SYMBOLS
    ]
    decision = _replication_decision(results)

    summary = {
        "artifact_version": (
            "task-106-us-bandi-russell-replication-v1"
        ),
        "task": 106,
        "role": "secondary_replication_only",
        "provider_calls": 0,
        "panel": {
            "prior_session": sessions[0],
            "first_audit_session": sessions[1],
            "last_audit_session": sessions[-1],
            "audit_sessions_per_symbol": 252,
            "symbols": list(SYMBOLS),
        },
        "symbol_results": results,
        "replication": decision,
        "primary_decision_override_allowed": False,
        "formula_cross_check": "pass",
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_PATH, summary)
    _write_json(
        DAILY_PATH,
        {
            "artifact_version": (
                "task-106-us-bandi-russell-replication-daily-v1"
            ),
            "daily_values": daily,
        },
    )


def _load_evidence(
    root: Path,
) -> dict[
    tuple[str, str],
    tuple[tuple[dict[str, Any], ...], Any],
]:
    result = {}
    receipts = sorted(
        root.glob(
            "evidence/alpaca/*/*/*/*/acceptance-receipt.json"
        )
    )
    if len(receipts) != 506:
        raise RuntimeError(
            f"task106r_unexpected_receipt_count:{len(receipts)}"
        )

    for receipt_path in receipts:
        receipt = _load_json(receipt_path)
        if receipt.get("provider") != "alpaca":
            raise RuntimeError("task106r_wrong_provider")
        if receipt.get("price_basis") != "split_adjusted":
            raise RuntimeError("task106r_wrong_price_basis")
        raw_path = receipt_path.parent / "raw-response.bin"
        raw_bytes = raw_path.read_bytes()
        if sha256(raw_bytes).hexdigest() != receipt.get(
            "raw_artifact_sha256"
        ):
            raise RuntimeError(
                "task106r_raw_hash_mismatch"
            )
        payload = json.loads(raw_bytes)
        bars = decode_alpaca_stock_bars(
            payload=payload,
            expected_source_symbol=receipt["source_symbol"],
            security=receipt["security"],
            price_basis="split_adjusted",
        )
        if len(bars) != receipt["observed_minute_count"]:
            raise RuntimeError("task106r_bar_count_mismatch")

        session_start_text = receipt[
            "first_bar_start_utc"
        ]
        from datetime import datetime

        session_start = datetime.fromisoformat(
            session_start_text
        )
        key = (
            receipt["source_symbol"],
            receipt["session_date"],
        )
        if key in result:
            raise RuntimeError("task106r_duplicate_symbol_session")
        result[key] = (bars, session_start)
    return result


def _calculate_session(
    *,
    symbol: str,
    session: str,
    bars: tuple[dict[str, Any], ...],
    session_start: Any,
) -> dict[str, Any]:
    prices_1m = (
        float(bars[0]["open"]),
        *tuple(float(bar["close"]) for bar in bars),
    )
    returns_1m = _log_returns(prices_1m)
    nonzero_1m = tuple(
        value for value in returns_1m if value != 0.0
    )
    if not nonzero_1m:
        raise RuntimeError(
            f"task106r_no_nonzero_1m:{symbol}:{session}"
        )
    omega2_hat = (
        math.fsum(value * value for value in nonzero_1m)
        / (2.0 * len(nonzero_1m))
    )

    bars_10m = aggregate_minute_bars(
        bars,
        10,
        session_start,
    )
    prices_10m = (
        float(bars_10m[0]["open"]),
        *tuple(float(bar["close"]) for bar in bars_10m),
    )
    returns_10m = _log_returns(prices_10m)
    nonzero_10m = tuple(
        value for value in returns_10m if value != 0.0
    )
    if not nonzero_10m:
        raise RuntimeError(
            f"task106r_no_nonzero_10m:{symbol}:{session}"
        )
    q10_hat = (
        len(nonzero_10m)
        / 3.0
        * math.fsum(value**4 for value in nonzero_10m)
    )

    n_opt = (
        q10_hat / ((2.0 * omega2_hat) ** 2)
    ) ** (1.0 / 3.0)
    session_minutes = len(bars)
    candidate_mse = {
        f"{interval}m": _candidate_mse(
            q10_hat=q10_hat,
            omega2_hat=omega2_hat,
            observation_count=session_minutes / interval,
        )
        for interval in CANDIDATE_INTERVALS
    }
    minimum = min(candidate_mse.values())
    winners = [
        grid
        for grid, value in candidate_mse.items()
        if value == minimum
    ]
    if len(winners) != 1:
        raise RuntimeError(
            f"task106r_daily_tie:{symbol}:{session}"
        )

    return {
        "session_date": session,
        "session_minutes": session_minutes,
        "omega2_hat": omega2_hat,
        "q10_hat": q10_hat,
        "n_opt": n_opt,
        "delta_opt_minutes": session_minutes / n_opt,
        "candidate_mse": candidate_mse,
        "candidate_mse_ratio_to_daily_min": {
            grid: value / minimum
            for grid, value in candidate_mse.items()
        },
        "daily_mse_winner": winners[0],
    }


def _summarize_symbol(
    symbol: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(rows) != 252:
        raise RuntimeError(
            f"task106r_wrong_row_count:{symbol}:{len(rows)}"
        )
    grids = ("5m", "10m", "15m")
    median_ratio = {
        grid: statistics.median(
            row["candidate_mse_ratio_to_daily_min"][grid]
            for row in rows
        )
        for grid in grids
    }
    wins = {
        grid: sum(
            row["daily_mse_winner"] == grid
            for row in rows
        )
        for grid in grids
    }
    minimum = min(median_ratio.values())
    candidates = [
        grid
        for grid, value in median_ratio.items()
        if value == minimum
    ]
    if len(candidates) != 1:
        symbol_candidate = "TIE"
    else:
        symbol_candidate = candidates[0]

    max_wins = max(wins.values())
    win_candidates = [
        grid for grid, count in wins.items()
        if count == max_wins
    ]
    support_candidate = (
        win_candidates[0]
        if len(win_candidates) == 1
        else "TIE"
    )

    delta = sorted(
        float(row["delta_opt_minutes"])
        for row in rows
    )
    return {
        "symbol": symbol,
        "median_candidate_mse_ratio": median_ratio,
        "candidate_win_counts": wins,
        "symbol_candidate_by_median_mse_ratio": (
            symbol_candidate
        ),
        "supporting_candidate_by_win_count": (
            support_candidate
        ),
        "support_consistent": (
            symbol_candidate == support_candidate
        ),
        "delta_opt_minutes": {
            "p10": _quantile(delta, 0.10),
            "p25": _quantile(delta, 0.25),
            "median": statistics.median(delta),
            "p75": _quantile(delta, 0.75),
            "p90": _quantile(delta, 0.90),
            "mean": statistics.fmean(delta),
        },
    }


def _replication_decision(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = {
        result["symbol_candidate_by_median_mse_ratio"]
        for result in results
    }
    unanimous = (
        len(candidates) == 1
        and "TIE" not in candidates
    )
    support = all(
        result["support_consistent"]
        for result in results
    )
    candidate = (
        next(iter(candidates))
        if unanimous
        else "INCONCLUSIVE"
    )
    return {
        "unanimous_symbol_candidate": unanimous,
        "supporting_win_count_consistent": support,
        "replication_candidate": (
            candidate
            if unanimous and support
            else "INCONCLUSIVE"
        ),
    }


def _cross_check_primary_formula() -> None:
    primary_daily = _load_json(
        TASK106_ROOT / "daily-values.json"
    )
    evidence = _load_evidence(TASK106_ROOT)
    daily = primary_daily.get("daily_values")
    if not isinstance(daily, dict):
        raise RuntimeError(
            "task106r_invalid_primary_daily"
        )

    for symbol in SYMBOLS:
        rows = daily.get(symbol)
        if not isinstance(rows, list) or not rows:
            raise RuntimeError(
                f"task106r_missing_primary_rows:{symbol}"
            )
        expected = rows[0]
        session = expected["session_date"]
        bars, session_start = evidence[(symbol, session)]
        actual = _calculate_session(
            symbol=symbol,
            session=session,
            bars=bars,
            session_start=session_start,
        )
        for key in (
            "omega2_hat",
            "q10_hat",
            "n_opt",
            "delta_opt_minutes",
        ):
            if not math.isclose(
                float(actual[key]),
                float(expected[key]),
                rel_tol=1e-12,
                abs_tol=1e-15,
            ):
                raise RuntimeError(
                    f"task106r_formula_crosscheck:{symbol}:{key}"
                )


def _candidate_mse(
    *,
    q10_hat: float,
    omega2_hat: float,
    observation_count: float,
) -> float:
    return (
        2.0 * q10_hat / observation_count
        + 4.0
        * observation_count**2
        * omega2_hat**2
    )


def _log_returns(
    prices: tuple[float, ...],
) -> tuple[float, ...]:
    return tuple(
        math.log(current / previous)
        for previous, current in zip(
            prices,
            prices[1:],
        )
    )


def _quantile(
    sorted_values: list[float],
    probability: float,
) -> float:
    position = (
        len(sorted_values) - 1
    ) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return (
        sorted_values[lower] * (1.0 - fraction)
        + sorted_values[upper] * fraction
    )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(
            f"task106r_invalid_json:{path}"
        )
    return value


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
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
