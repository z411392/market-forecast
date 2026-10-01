import json
import math
import os
import statistics
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import httpx

from libs.market_data.adapters.driven.filesystem_provider_capture_evidence_adapter import (
    FilesystemProviderCaptureEvidenceAdapter,
)
from libs.market_data.adapters.driven.httpx_alpaca_provider_raw_response_adapter import (
    HttpxAlpacaProviderRawResponseAdapter,
)
from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.assemble_provider_capture_sample import (
    assemble_provider_capture_sample,
)
from libs.market_data.services.build_alpaca_historical_bars_request import (
    build_alpaca_historical_bars_request,
)
from libs.market_data.services.build_provider_capture_acceptance_receipt import (
    build_provider_capture_acceptance_receipt,
)
from libs.realized_variance.domain.services.aggregate_minute_bars import (
    aggregate_minute_bars,
)

SYMBOLS = ("AAPL", "NVDA")
END_SESSION = date(2025, 9, 22)
AUDIT_SESSION_COUNT = 252
CANDIDATE_INTERVALS = (5, 10, 15)
REQUEST_SLEEP_SECONDS = 0.5

OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/"
    "task-106-us-bandi-russell-optimal-sampling"
)
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"


def main() -> None:
    api_key_id = _required_secret(
        "MARKET_FORECAST_ALPACA_API_KEY_ID"
    )
    secret_key = _required_secret(
        "MARKET_FORECAST_ALPACA_SECRET_KEY"
    )
    retrieval_date = datetime.now(timezone.utc).date()

    calendar = xcals.get_calendar("XNAS")
    sessions = tuple(
        timestamp.date()
        for timestamp in calendar.sessions_window(
            END_SESSION.isoformat(),
            -(AUDIT_SESSION_COUNT + 1),
        )
    )
    if len(sessions) != AUDIT_SESSION_COUNT + 1:
        raise RuntimeError(
            f"task106_unexpected_session_count:{len(sessions)}"
        )
    if sessions[0] != date(2024, 9, 18):
        raise RuntimeError(
            f"task106_unexpected_prior_session:{sessions[0]}"
        )
    if sessions[1] != date(2024, 9, 19):
        raise RuntimeError(
            f"task106_unexpected_first_audit_session:{sessions[1]}"
        )
    if sessions[-1] != END_SESSION:
        raise RuntimeError(
            f"task106_unexpected_last_session:{sessions[-1]}"
        )

    if OUTPUT_ROOT.exists():
        import shutil

        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    persist = FilesystemProviderCaptureEvidenceAdapter(
        EVIDENCE_ROOT
    )
    securities = {
        symbol: _security(symbol)
        for symbol in SYMBOLS
    }
    daily: dict[str, list[dict[str, Any]]] = {
        symbol: [] for symbol in SYMBOLS
    }

    summary: dict[str, Any] = {
        "artifact_version": (
            "task-106-us-bandi-russell-optimal-sampling-v1"
        ),
        "task": 106,
        "parent_task": 12,
        "status": "running",
        "provider": "alpaca",
        "feed": "sip",
        "timeframe": "1Min",
        "price_basis": "split_adjusted",
        "calendar": "XNAS",
        "symbols": list(SYMBOLS),
        "prior_session": sessions[0].isoformat(),
        "first_audit_session": sessions[1].isoformat(),
        "last_audit_session": sessions[-1].isoformat(),
        "audit_sessions_per_symbol": AUDIT_SESSION_COUNT,
        "retrieval_date": retrieval_date.isoformat(),
        "request_sleep_seconds": REQUEST_SLEEP_SECONDS,
        "formula": {
            "noise_variance": (
                "sum(nonzero_1m_return^2)/(2*n_nonzero_1m)"
            ),
            "quarticity": (
                "(n_nonzero_10m/3)*sum(nonzero_10m_return^4)"
            ),
            "n_opt": (
                "[Q10_hat/(2*omega2_hat)^2]^(1/3)"
            ),
            "candidate_mse": (
                "2*Q10_hat/n_c + 4*n_c^2*omega2_hat^2"
            ),
        },
        "symbol_results": [],
    }
    _write_json(SUMMARY_PATH, summary)

    with httpx.Client(timeout=30.0) as client:
        fetch = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id=api_key_id,
            secret_key=secret_key,
            allow_live=True,
        )

        source_counts = {
            symbol: {
                "symbol": symbol,
                "accepted_source_sessions": 0,
                "gap_count": 0,
                "missing_grid_minutes": 0,
                "full_sessions": 0,
                "early_close_sessions": 0,
            }
            for symbol in SYMBOLS
        }

        for session_index, session_date in enumerate(sessions):
            label = session_date.isoformat()
            session_open = calendar.session_open(
                label
            ).to_pydatetime()
            session_close = calendar.session_close(
                label
            ).to_pydatetime()
            expected_count = int(
                (
                    session_close - session_open
                ).total_seconds()
                // 60
            )
            if expected_count not in (210, 390):
                raise RuntimeError(
                    "task106_unexpected_session_minutes:"
                    f"{label}:{expected_count}"
                )

            for symbol in SYMBOLS:
                request = build_alpaca_historical_bars_request(
                    source_symbol=symbol,
                    session_start_utc=session_open,
                    session_end_utc_exclusive=session_close,
                    price_basis="split_adjusted",
                )
                raw_response = fetch(
                    provider="alpaca",
                    request=request,
                )
                manifest, bars = assemble_provider_capture_sample(
                    provider="alpaca",
                    raw_response=raw_response,
                    source_symbol=symbol,
                    retrieval_date=retrieval_date,
                    security=securities[symbol],
                    session_date=session_date,
                    expected_session_start_utc=session_open,
                    expected_session_end_utc_exclusive=session_close,
                    expected_minute_count=expected_count,
                    price_basis="split_adjusted",
                )
                receipt = build_provider_capture_acceptance_receipt(
                    request=request,
                    manifest=manifest,
                    bars=bars,
                )
                persist(
                    raw_response=raw_response,
                    receipt=receipt,
                )

                source = source_counts[symbol]
                source["accepted_source_sessions"] += 1
                source["gap_count"] += receipt["gap_count"]
                source["missing_grid_minutes"] += receipt[
                    "missing_grid_minutes"
                ]
                if expected_count == 390:
                    source["full_sessions"] += 1
                else:
                    source["early_close_sessions"] += 1

                if session_index > 0:
                    daily[symbol].append(
                        _calculate_session(
                            symbol=symbol,
                            session_date=session_date,
                            session_start_utc=session_open,
                            bars=bars,
                        )
                    )

                _write_progress(
                    summary,
                    source_counts,
                    daily,
                )
                time.sleep(REQUEST_SLEEP_SECONDS)

    results = [
        _summarize_symbol(
            symbol=symbol,
            rows=daily[symbol],
            source=source_counts[symbol],
        )
        for symbol in SYMBOLS
    ]
    decision = _decision(results)

    summary["symbol_results"] = results
    summary["decision"] = decision
    summary["status"] = "accepted"
    _write_json(SUMMARY_PATH, summary)
    _write_json(
        DAILY_PATH,
        {
            "artifact_version": (
                "task-106-us-bandi-russell-daily-v1"
            ),
            "daily_values": daily,
        },
    )


def _calculate_session(
    *,
    symbol: str,
    session_date: date,
    session_start_utc: datetime,
    bars: tuple[CanonicalMinuteBar, ...],
) -> dict[str, Any]:
    prices_1m = (
        float(bars[0]["open"]),
        *tuple(float(bar["close"]) for bar in bars),
    )
    returns_1m = _log_returns(prices_1m)
    nonzero_1m = tuple(
        value
        for value in returns_1m
        if value != 0.0
    )
    if not nonzero_1m:
        raise RuntimeError(
            f"task106_no_nonzero_1m_returns:{symbol}:{session_date}"
        )

    omega2_hat = (
        math.fsum(value * value for value in nonzero_1m)
        / (2.0 * len(nonzero_1m))
    )
    if not math.isfinite(omega2_hat) or omega2_hat <= 0.0:
        raise RuntimeError(
            f"task106_invalid_noise_variance:{symbol}:{session_date}"
        )

    bars_10m = aggregate_minute_bars(
        bars,
        10,
        session_start_utc,
    )
    prices_10m = (
        float(bars_10m[0]["open"]),
        *tuple(float(bar["close"]) for bar in bars_10m),
    )
    returns_10m = _log_returns(prices_10m)
    nonzero_10m = tuple(
        value
        for value in returns_10m
        if value != 0.0
    )
    if not nonzero_10m:
        raise RuntimeError(
            f"task106_no_nonzero_10m_returns:{symbol}:{session_date}"
        )

    q10_hat = (
        len(nonzero_10m)
        / 3.0
        * math.fsum(
            value**4
            for value in nonzero_10m
        )
    )
    if not math.isfinite(q10_hat) or q10_hat <= 0.0:
        raise RuntimeError(
            f"task106_invalid_quarticity:{symbol}:{session_date}"
        )

    n_opt = (
        q10_hat
        / ((2.0 * omega2_hat) ** 2)
    ) ** (1.0 / 3.0)
    if not math.isfinite(n_opt) or n_opt <= 0.0:
        raise RuntimeError(
            f"task106_invalid_n_opt:{symbol}:{session_date}"
        )

    session_minutes = len(bars)
    delta_opt_minutes = session_minutes / n_opt

    candidate_mse = {
        f"{interval}m": _candidate_mse(
            q10_hat=q10_hat,
            omega2_hat=omega2_hat,
            observation_count=(
                session_minutes / interval
            ),
        )
        for interval in CANDIDATE_INTERVALS
    }
    minimum_mse = min(candidate_mse.values())
    winners = [
        grid
        for grid, value in candidate_mse.items()
        if value == minimum_mse
    ]
    if len(winners) != 1:
        raise RuntimeError(
            f"task106_candidate_mse_tie:{symbol}:{session_date}"
        )
    winner = winners[0]

    return {
        "session_date": session_date.isoformat(),
        "session_minutes": session_minutes,
        "nonzero_1m_return_count": len(nonzero_1m),
        "zero_1m_return_count": (
            len(returns_1m) - len(nonzero_1m)
        ),
        "nonzero_10m_return_count": len(nonzero_10m),
        "omega2_hat": omega2_hat,
        "q10_hat": q10_hat,
        "n_opt": n_opt,
        "delta_opt_minutes": delta_opt_minutes,
        "candidate_mse": candidate_mse,
        "candidate_mse_ratio_to_daily_min": {
            grid: value / minimum_mse
            for grid, value in candidate_mse.items()
        },
        "daily_mse_winner": winner,
    }


def _summarize_symbol(
    *,
    symbol: str,
    rows: list[dict[str, Any]],
    source: dict[str, Any],
) -> dict[str, Any]:
    if len(rows) != AUDIT_SESSION_COUNT:
        raise RuntimeError(
            f"task106_wrong_audit_count:{symbol}:{len(rows)}"
        )

    delta = [
        float(row["delta_opt_minutes"])
        for row in rows
    ]
    sorted_delta = sorted(delta)

    grids = tuple(
        f"{interval}m"
        for interval in CANDIDATE_INTERVALS
    )
    median_mse_ratio = {
        grid: statistics.median(
            float(
                row[
                    "candidate_mse_ratio_to_daily_min"
                ][grid]
            )
            for row in rows
        )
        for grid in grids
    }
    mean_mse = {
        grid: statistics.fmean(
            float(row["candidate_mse"][grid])
            for row in rows
        )
        for grid in grids
    }
    win_counts = {
        grid: sum(
            row["daily_mse_winner"] == grid
            for row in rows
        )
        for grid in grids
    }

    minimum_ratio = min(median_mse_ratio.values())
    ratio_winners = [
        grid
        for grid, value in median_mse_ratio.items()
        if value == minimum_ratio
    ]
    if len(ratio_winners) != 1:
        raise RuntimeError(
            f"task106_symbol_median_mse_tie:{symbol}"
        )
    symbol_candidate = ratio_winners[0]

    max_wins = max(win_counts.values())
    support_winners = [
        grid
        for grid, count in win_counts.items()
        if count == max_wins
    ]
    supporting_candidate = (
        support_winners[0]
        if len(support_winners) == 1
        else "TIE"
    )

    return {
        **source,
        "audit_session_count": len(rows),
        "delta_opt_minutes": {
            "p10": _quantile(
                sorted_delta,
                0.10,
            ),
            "p25": _quantile(
                sorted_delta,
                0.25,
            ),
            "median": statistics.median(
                sorted_delta
            ),
            "p75": _quantile(
                sorted_delta,
                0.75,
            ),
            "p90": _quantile(
                sorted_delta,
                0.90,
            ),
            "mean": statistics.fmean(
                sorted_delta
            ),
        },
        "median_candidate_mse_ratio": median_mse_ratio,
        "mean_candidate_mse": mean_mse,
        "candidate_win_counts": win_counts,
        "symbol_candidate_by_median_mse_ratio": (
            symbol_candidate
        ),
        "supporting_candidate_by_win_count": (
            supporting_candidate
        ),
        "support_consistent": (
            supporting_candidate == symbol_candidate
        ),
        "zero_1m_return_count": {
            "total": sum(
                int(row["zero_1m_return_count"])
                for row in rows
            ),
            "median_per_session": statistics.median(
                int(row["zero_1m_return_count"])
                for row in rows
            ),
        },
    }


def _decision(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = {
        result["symbol_candidate_by_median_mse_ratio"]
        for result in results
    }
    support_ok = all(
        bool(result["support_consistent"])
        for result in results
    )
    unanimous = len(candidates) == 1
    candidate = (
        next(iter(candidates))
        if unanimous
        else "INCONCLUSIVE"
    )
    freeze = unanimous and support_ok

    return {
        "freeze_allowed": freeze,
        "us_canonical_sampling": (
            candidate
            if freeze
            else "INCONCLUSIVE"
        ),
        "unanimous_symbol_candidate": unanimous,
        "supporting_win_count_consistent": support_ok,
        "forecast_score_used": False,
        "primary_panel_only": True,
        "task97_replication_not_used_for_primary_decision": True,
    }


def _candidate_mse(
    *,
    q10_hat: float,
    omega2_hat: float,
    observation_count: float,
) -> float:
    value = (
        2.0 * q10_hat / observation_count
        + 4.0
        * observation_count**2
        * omega2_hat**2
    )
    if not math.isfinite(value) or value <= 0.0:
        raise RuntimeError("task106_invalid_candidate_mse")
    return value


def _log_returns(
    prices: tuple[float, ...],
) -> tuple[float, ...]:
    if len(prices) < 2:
        raise RuntimeError("task106_insufficient_prices")
    result = []
    for previous, current in zip(
        prices,
        prices[1:],
    ):
        if (
            not math.isfinite(previous)
            or not math.isfinite(current)
            or previous <= 0.0
            or current <= 0.0
        ):
            raise RuntimeError(
                "task106_invalid_price"
            )
        result.append(
            math.log(current / previous)
        )
    return tuple(result)


def _quantile(
    sorted_values: list[float],
    probability: float,
) -> float:
    if not sorted_values:
        raise RuntimeError("task106_empty_quantile")
    if not 0.0 <= probability <= 1.0:
        raise RuntimeError(
            "task106_invalid_quantile_probability"
        )
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (
        (len(sorted_values) - 1)
        * probability
    )
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return (
        sorted_values[lower]
        * (1.0 - fraction)
        + sorted_values[upper]
        * fraction
    )


def _security(
    symbol: str,
) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _write_progress(
    summary: dict[str, Any],
    source_counts: dict[str, dict[str, Any]],
    daily: dict[str, list[dict[str, Any]]],
) -> None:
    summary["progress"] = {
        symbol: {
            **source_counts[symbol],
            "computed_audit_sessions": len(
                daily[symbol]
            ),
        }
        for symbol in SYMBOLS
    }
    _write_json(SUMMARY_PATH, summary)


def _required_secret(
    name: str,
) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
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
