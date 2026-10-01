import json
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
from libs.realized_variance.domain.services.build_measurement_audit_rows import (
    build_measurement_audit_rows,
)
from libs.realized_variance.domain.services.calculate_daily_realized_measures import (
    calculate_daily_realized_measures,
)
from libs.realized_variance.domain.services.calculate_intraday_realized_measures import (
    calculate_intraday_realized_measures,
)
from libs.realized_variance.domain.services.calculate_overnight_log_return import (
    calculate_overnight_log_return,
)
from libs.realized_variance.domain.services.summarize_measurement_audit import (
    summarize_measurement_audit,
)

SYMBOLS = ("AAPL", "NVDA")
END_SESSION = date(2026, 9, 24)
AUDIT_SESSION_COUNT = 252
SAMPLING_INTERVALS = (5, 10, 15)
REQUEST_SLEEP_SECONDS = 0.5
OUTPUT_ROOT = Path("artifacts/private/provider-captures/task-97-us-rv-measurement-audit")
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"


def main() -> None:
    api_key_id = _required_secret("MARKET_FORECAST_ALPACA_API_KEY_ID")
    secret_key = _required_secret("MARKET_FORECAST_ALPACA_SECRET_KEY")
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
        raise RuntimeError("unexpected_xnas_session_count")
    if sessions[-1] != END_SESSION:
        raise RuntimeError("unexpected_xnas_end_session")

    security_by_symbol = {symbol: _security(symbol) for symbol in SYMBOLS}
    persist = FilesystemProviderCaptureEvidenceAdapter(EVIDENCE_ROOT)

    summary: dict[str, Any] = {
        "task": 97,
        "parent_task": 12,
        "provider": "alpaca",
        "feed": "sip",
        "timeframe": "1Min",
        "price_basis": "split_adjusted",
        "calendar": "XNAS",
        "symbols": list(SYMBOLS),
        "prior_session_for_first_overnight": sessions[0].isoformat(),
        "first_audit_session": sessions[1].isoformat(),
        "last_audit_session": sessions[-1].isoformat(),
        "audit_session_count": AUDIT_SESSION_COUNT,
        "retrieval_date": retrieval_date.isoformat(),
        "request_sleep_seconds": REQUEST_SLEEP_SECONDS,
        "status": "running",
        "symbols_result": [],
    }
    _write_json(SUMMARY_PATH, summary)

    measurements_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in SYMBOLS}
    daily_rows: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in SYMBOLS}
    previous_close: dict[str, float] = {}

    with httpx.Client(timeout=30.0) as client:
        fetch = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id=api_key_id,
            secret_key=secret_key,
            allow_live=True,
        )

        symbol_results = {
            symbol: {
                "symbol": symbol,
                "status": "fetching",
                "accepted_session_count": 0,
                "gap_count": 0,
                "missing_grid_minutes": 0,
                "full_session_count": 0,
                "early_close_session_count": 0,
                "request_receipts": [],
            }
            for symbol in SYMBOLS
        }
        summary["symbols_result"] = [symbol_results[symbol] for symbol in SYMBOLS]
        _write_json(SUMMARY_PATH, summary)

        for session_index, session_date in enumerate(sessions):
            label = session_date.isoformat()
            session_open = calendar.session_open(label).to_pydatetime()
            session_close = calendar.session_close(label).to_pydatetime()
            expected_count = int((session_close - session_open).total_seconds() // 60)
            if expected_count not in (210, 390):
                raise RuntimeError(f"unexpected_xnas_session_minutes:{label}:{expected_count}")

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
                    security=security_by_symbol[symbol],
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

                symbol_result = symbol_results[symbol]
                symbol_result["accepted_session_count"] += 1
                symbol_result["gap_count"] += receipt["gap_count"]
                symbol_result["missing_grid_minutes"] += receipt["missing_grid_minutes"]
                if expected_count == 390:
                    symbol_result["full_session_count"] += 1
                else:
                    symbol_result["early_close_session_count"] += 1
                symbol_result["request_receipts"].append(
                    {
                        "session_date": session_date.isoformat(),
                        "raw_artifact_sha256": receipt["raw_artifact_sha256"],
                        "expected_minute_count": receipt["expected_minute_count"],
                        "observed_minute_count": receipt["observed_minute_count"],
                        "gap_count": receipt["gap_count"],
                        "missing_grid_minutes": receipt["missing_grid_minutes"],
                    }
                )

                if session_index == 0:
                    previous_close[symbol] = bars[-1]["close"]
                else:
                    overnight = calculate_overnight_log_return(
                        previous_close[symbol],
                        bars[0]["open"],
                    )
                    session_daily: dict[str, Any] = {
                        "session_date": session_date.isoformat(),
                        "overnight_log_return": overnight,
                    }
                    for interval in SAMPLING_INTERVALS:
                        aggregated = aggregate_minute_bars(
                            bars,
                            interval,
                            session_open,
                        )
                        intraday = calculate_intraday_realized_measures(aggregated)
                        daily = calculate_daily_realized_measures(
                            intraday,
                            overnight,
                        )
                        measurements_by_symbol[symbol].append(daily)
                        session_daily[f"{interval}m"] = {
                            "whole_day_variance": daily["whole_day_variance"],
                            "regular_session_variance": daily["regular_session_variance"],
                            "overnight_variance": daily["overnight_variance"],
                            "observation_count": daily["observation_count"],
                        }
                    daily_rows[symbol].append(session_daily)
                    previous_close[symbol] = bars[-1]["close"]

                _write_json(SUMMARY_PATH, summary)
                time.sleep(REQUEST_SLEEP_SECONDS)

    for symbol in SYMBOLS:
        symbol_result = next(item for item in summary["symbols_result"] if item["symbol"] == symbol)
        rows = build_measurement_audit_rows(measurements_by_symbol[symbol])
        audit_summary = summarize_measurement_audit(rows)
        if len(rows) != AUDIT_SESSION_COUNT:
            raise RuntimeError(f"unexpected_us_audit_row_count:{symbol}:{len(rows)}")

        ordered = sorted(
            rows,
            key=lambda row: max(
                row["abs_log_gap_5m_10m"],
                row["abs_log_gap_5m_15m"],
            ),
            reverse=True,
        )
        monotonic_5_10 = sum(row["whole_day_variance_5m"] > row["whole_day_variance_10m"] for row in rows)
        monotonic_10_15 = sum(row["whole_day_variance_10m"] > row["whole_day_variance_15m"] for row in rows)
        strict_descending = sum(
            row["whole_day_variance_5m"] > row["whole_day_variance_10m"] > row["whole_day_variance_15m"]
            for row in rows
        )

        symbol_result.update(
            {
                "status": "accepted",
                "audit_row_count": len(rows),
                "measurement_audit_summary": _serialize_audit_summary(audit_summary),
                "monotonic_frequency": {
                    "rv_5m_gt_10m_pct": monotonic_5_10 / len(rows) * 100.0,
                    "rv_10m_gt_15m_pct": monotonic_10_15 / len(rows) * 100.0,
                    "rv_5m_gt_10m_gt_15m_pct": strict_descending / len(rows) * 100.0,
                },
                "top_abs_log_gap_sessions": [
                    {
                        "session_date": row["session_date"].isoformat(),
                        "whole_day_variance_5m": row["whole_day_variance_5m"],
                        "whole_day_variance_10m": row["whole_day_variance_10m"],
                        "whole_day_variance_15m": row["whole_day_variance_15m"],
                        "log_ratio_5m_10m": row["log_ratio_5m_10m"],
                        "log_ratio_5m_15m": row["log_ratio_5m_15m"],
                        "abs_log_gap_5m_10m": row["abs_log_gap_5m_10m"],
                        "abs_log_gap_5m_15m": row["abs_log_gap_5m_15m"],
                    }
                    for row in ordered[:10]
                ],
            }
        )

    summary["panel_median_metrics"] = _panel_medians(summary["symbols_result"])
    summary["decision_diagnostic"] = _decision_diagnostic(summary["symbols_result"])
    summary["status"] = "accepted"
    _write_json(SUMMARY_PATH, summary)
    _write_json(
        DAILY_PATH,
        {
            "task": 97,
            "provider": "alpaca",
            "price_basis": "split_adjusted",
            "daily_values": daily_rows,
        },
    )


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _serialize_audit_summary(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["security"] = dict(value["security"])
    result["first_session_date"] = value["first_session_date"].isoformat()
    result["last_session_date"] = value["last_session_date"].isoformat()
    return result


def _panel_medians(
    symbol_results: list[dict[str, Any]],
) -> dict[str, float]:
    keys = (
        "pearson_log_rv_5m_10m",
        "pearson_log_rv_5m_15m",
        "spearman_rv_5m_10m",
        "spearman_rv_5m_15m",
        "geometric_bias_5m_vs_10m_pct",
        "geometric_bias_5m_vs_15m_pct",
        "mean_abs_log_gap_5m_10m",
        "mean_abs_log_gap_5m_15m",
    )
    return {
        key: statistics.median(float(result["measurement_audit_summary"][key]) for result in symbol_results)
        for key in keys
    }


def _decision_diagnostic(
    symbol_results: list[dict[str, Any]],
) -> dict[str, Any]:
    systematic_monotone_inflation = all(
        result["measurement_audit_summary"]["geometric_bias_5m_vs_10m_pct"] > 0.0
        and result["measurement_audit_summary"]["geometric_bias_5m_vs_15m_pct"]
        > result["measurement_audit_summary"]["geometric_bias_5m_vs_10m_pct"]
        for result in symbol_results
    )
    return {
        "systematic_monotone_level_inflation": (systematic_monotone_inflation),
        "rule_if_true": "US_CANONICAL_SAMPLING_INCONCLUSIVE",
        "rule_if_false": "US_CANONICAL_SAMPLING_5M_CANDIDATE",
        "forecast_score_used": False,
    }


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


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
