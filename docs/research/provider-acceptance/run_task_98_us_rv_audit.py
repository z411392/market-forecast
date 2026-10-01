import json
import os
import shutil
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
from libs.market_data.services.build_provider_request_sha256 import (
    build_provider_request_sha256,
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
PRICE_BASIS = "split_adjusted"
REQUEST_SLEEP_SECONDS = 0.35
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-98-us-rv-audit"
)
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"


def main() -> None:
    key_id = _required_secret("MARKET_FORECAST_ALPACA_API_KEY_ID")
    secret = _required_secret("MARKET_FORECAST_ALPACA_SECRET_KEY")
    retrieval_date = datetime.now(timezone.utc).date()

    calendar = xcals.get_calendar("XNAS")
    sessions = tuple(
        timestamp.date()
        for timestamp in calendar.sessions_window(
            END_SESSION.isoformat(),
            -253,
        )
    )
    if len(sessions) != AUDIT_SESSION_COUNT + 1:
        raise RuntimeError("unexpected_xnas_session_window_length")
    if sessions[0] != date(2025, 9, 23):
        raise RuntimeError("unexpected_xnas_prior_session")
    if sessions[1] != date(2025, 9, 24):
        raise RuntimeError("unexpected_xnas_first_audit_session")
    if sessions[-1] != END_SESSION:
        raise RuntimeError("unexpected_xnas_end_session")

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "task": 98,
        "provider": "alpaca",
        "feed": "sip",
        "timeframe": "1Min",
        "price_basis": PRICE_BASIS,
        "calendar": "XNAS",
        "retrieval_date": retrieval_date.isoformat(),
        "prior_session_for_first_overnight": sessions[0].isoformat(),
        "first_audit_session": sessions[1].isoformat(),
        "last_audit_session": sessions[-1].isoformat(),
        "audit_session_count": AUDIT_SESSION_COUNT,
        "symbols": list(SYMBOLS),
        "status": "running",
        "symbols_result": [],
    }
    _write_summary(summary)

    with httpx.Client(timeout=30.0) as client:
        fetch = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id=key_id,
            secret_key=secret,
            allow_live=True,
        )
        persist = FilesystemProviderCaptureEvidenceAdapter(
            EVIDENCE_ROOT
        )

        for symbol in SYMBOLS:
            security = _security(symbol)
            symbol_result: dict[str, Any] = {
                "symbol": symbol,
                "status": "fetching",
                "accepted_session_count": 0,
                "captures": [],
            }
            summary["symbols_result"].append(symbol_result)
            _write_summary(summary)

            by_session: dict[date, tuple[Any, ...]] = {}
            for session_date in sessions:
                start, end = _session_bounds(calendar, session_date)
                expected_count = int(
                    (end - start).total_seconds() // 60
                )
                request = build_alpaca_historical_bars_request(
                    source_symbol=symbol,
                    session_start_utc=start,
                    session_end_utc_exclusive=end,
                    price_basis=PRICE_BASIS,
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
                    security=security,
                    session_date=session_date,
                    expected_session_start_utc=start,
                    expected_session_end_utc_exclusive=end,
                    expected_minute_count=expected_count,
                    price_basis=PRICE_BASIS,
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

                _validate_contiguous_session(
                    bars=bars,
                    expected_start=start,
                    expected_count=expected_count,
                )
                by_session[session_date] = bars
                symbol_result["accepted_session_count"] += 1
                symbol_result["captures"].append(
                    {
                        "session_date": session_date.isoformat(),
                        "expected_minute_count": expected_count,
                        "observed_minute_count": len(bars),
                        "request_sha256": build_provider_request_sha256(
                            request
                        ),
                        "raw_artifact_sha256": receipt[
                            "raw_artifact_sha256"
                        ],
                        "gap_count": receipt["gap_count"],
                    }
                )
                _write_summary(summary)
                time.sleep(REQUEST_SLEEP_SECONDS)

            measurements = []
            overnight_share_by_interval: dict[int, list[float]] = {
                5: [],
                10: [],
                15: [],
            }
            previous_close = by_session[sessions[0]][-1]["close"]

            for session_date in sessions[1:]:
                bars = by_session[session_date]
                current_open = bars[0]["open"]
                overnight_log_return = calculate_overnight_log_return(
                    previous_close,
                    current_open,
                )
                start, _ = _session_bounds(calendar, session_date)

                for interval in (5, 10, 15):
                    aggregated = aggregate_minute_bars(
                        bars,
                        interval,
                        start,
                    )
                    intraday = calculate_intraday_realized_measures(
                        aggregated
                    )
                    daily = calculate_daily_realized_measures(
                        intraday,
                        overnight_log_return,
                    )
                    measurements.append(daily)
                    if daily["whole_day_variance"] > 0.0:
                        overnight_share_by_interval[interval].append(
                            daily["overnight_variance"]
                            / daily["whole_day_variance"]
                        )

                previous_close = bars[-1]["close"]

            rows = build_measurement_audit_rows(measurements)
            if len(rows) != AUDIT_SESSION_COUNT:
                raise RuntimeError(
                    f"unexpected_audit_row_count:{symbol}:{len(rows)}"
                )
            audit_summary = summarize_measurement_audit(rows)
            ordered_outliers = sorted(
                rows,
                key=lambda row: max(
                    row["abs_log_gap_5m_10m"],
                    row["abs_log_gap_5m_15m"],
                ),
                reverse=True,
            )

            symbol_result.update(
                {
                    "status": "accepted",
                    "audit_row_count": len(rows),
                    "measurement_audit_summary": (
                        _serialize_audit_summary(audit_summary)
                    ),
                    "overnight_variance_share": {
                        str(interval): {
                            "mean": statistics.fmean(values),
                            "median": statistics.median(values),
                            "max": max(values),
                        }
                        for interval, values
                        in overnight_share_by_interval.items()
                    },
                    "top_abs_log_gap_sessions": [
                        {
                            "session_date": row[
                                "session_date"
                            ].isoformat(),
                            "whole_day_variance_5m": row[
                                "whole_day_variance_5m"
                            ],
                            "whole_day_variance_10m": row[
                                "whole_day_variance_10m"
                            ],
                            "whole_day_variance_15m": row[
                                "whole_day_variance_15m"
                            ],
                            "log_ratio_5m_10m": row[
                                "log_ratio_5m_10m"
                            ],
                            "log_ratio_5m_15m": row[
                                "log_ratio_5m_15m"
                            ],
                            "abs_log_gap_5m_10m": row[
                                "abs_log_gap_5m_10m"
                            ],
                            "abs_log_gap_5m_15m": row[
                                "abs_log_gap_5m_15m"
                            ],
                        }
                        for row in ordered_outliers[:10]
                    ],
                }
            )
            _write_summary(summary)

    accepted = [
        result
        for result in summary["symbols_result"]
        if result.get("status") == "accepted"
    ]
    if len(accepted) != len(SYMBOLS):
        raise RuntimeError("not_all_us_symbols_accepted")

    summary["panel_median_metrics"] = _panel_median_metrics(
        accepted
    )
    summary["decision_gate"] = _decision_gate(accepted)
    summary["status"] = "accepted"
    _write_summary(summary)


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _session_bounds(
    calendar: Any,
    session_date: date,
) -> tuple[datetime, datetime]:
    opening = calendar.session_open(
        session_date.isoformat()
    ).to_pydatetime()
    closing = calendar.session_close(
        session_date.isoformat()
    ).to_pydatetime()
    if opening.tzinfo is None or closing.tzinfo is None:
        raise RuntimeError("xnas_session_bound_not_aware")
    return (
        opening.astimezone(timezone.utc),
        closing.astimezone(timezone.utc),
    )


def _validate_contiguous_session(
    *,
    bars: tuple[Any, ...],
    expected_start: datetime,
    expected_count: int,
) -> None:
    if len(bars) != expected_count:
        raise RuntimeError("unexpected_us_minute_count")
    for index, bar in enumerate(bars):
        expected = expected_start + (
            index * (bars[1]["bar_start_utc"] - bars[0]["bar_start_utc"])
            if len(bars) > 1
            else index
        )
        if len(bars) > 1 and bar["bar_start_utc"] != expected:
            raise RuntimeError("non_contiguous_us_minute_bars")


def _serialize_audit_summary(
    value: dict[str, Any],
) -> dict[str, Any]:
    result = dict(value)
    result["security"] = dict(value["security"])
    result["first_session_date"] = value[
        "first_session_date"
    ].isoformat()
    result["last_session_date"] = value[
        "last_session_date"
    ].isoformat()
    return result


def _panel_median_metrics(
    accepted_results: list[dict[str, Any]],
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
        key: statistics.median(
            result["measurement_audit_summary"][key]
            for result in accepted_results
        )
        for key in keys
    }


def _decision_gate(
    accepted_results: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = []
    for result in accepted_results:
        metrics = result["measurement_audit_summary"]
        bias_10 = abs(
            metrics["geometric_bias_5m_vs_10m_pct"]
        )
        bias_15 = abs(
            metrics["geometric_bias_5m_vs_15m_pct"]
        )
        checks.append(
            {
                "symbol": result["symbol"],
                "abs_geometric_bias_5m_vs_10m_pct": bias_10,
                "abs_geometric_bias_5m_vs_15m_pct": bias_15,
                "below_10_pct_gate": (
                    bias_10 < 10.0 and bias_15 < 10.0
                ),
            }
        )

    passed = all(
        check["below_10_pct_gate"]
        for check in checks
    )
    return {
        "rule": (
            "freeze 5m only if both absolute geometric biases "
            "are <10% for every pilot symbol"
        ),
        "checks": checks,
        "passed": passed,
        "candidate_ruling": (
            "US_CANONICAL_SAMPLING_5M"
            if passed
            else "US_CANONICAL_SAMPLING_INCONCLUSIVE"
        ),
    }


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _write_summary(summary: dict[str, Any]) -> None:
    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
