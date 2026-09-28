import json
import math
import os
import statistics
import time as time_module
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock_time
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import shioaji as sj

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.decode_shioaji_stock_kbars import (
    decode_shioaji_stock_kbars,
)
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
)
from libs.realized_variance.domain.services.build_measurement_audit_rows import (
    build_measurement_audit_rows,
)
from libs.realized_variance.domain.services.build_xtai_sampling_prices import (
    build_xtai_sampling_prices,
)
from libs.realized_variance.domain.services.calculate_daily_realized_measures import (
    calculate_daily_realized_measures,
)
from libs.realized_variance.domain.services.calculate_intraday_realized_measures_from_sampled_prices import (
    calculate_intraday_realized_measures_from_sampled_prices,
)
from libs.realized_variance.domain.services.calculate_overnight_log_return import (
    calculate_overnight_log_return,
)
from libs.realized_variance.domain.services.summarize_measurement_audit import (
    summarize_measurement_audit,
)

SYMBOLS = ("2330", "2317", "2454")
END_SESSION = date(2026, 9, 24)
AUDIT_SESSION_COUNT = 252
QUERY_CHUNK_CALENDAR_DAYS = 28
OUTPUT = Path("artifacts/private/provider-captures/task-89-taiwan-rv-audit/summary.json")
FIELDS = ("ts", "Open", "High", "Low", "Close", "Volume", "Amount")
AD_HOC_FULL_DAY_CLOSURES = {
    date(2026, 7, 10): {
        "reason": "typhoon_bavi_twse_full_day_closure",
        "source": "https://www.twse.com.tw/en/clearing/suspended.html",
        "event_evidence": "https://www.cna.com.tw/news/afe/202607090360.aspx",
    }
}


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret("MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    calendar = xcals.get_calendar("XTAI")
    scheduled_window = tuple(
        timestamp.date()
        for timestamp in calendar.sessions_window(
            END_SESSION.isoformat(),
            -(AUDIT_SESSION_COUNT + 10),
        )
    )
    adjusted_window = tuple(
        session_date
        for session_date in scheduled_window
        if session_date not in AD_HOC_FULL_DAY_CLOSURES
    )
    expected_sessions = adjusted_window[-(AUDIT_SESSION_COUNT + 1) :]
    if len(expected_sessions) != AUDIT_SESSION_COUNT + 1:
        raise RuntimeError("unexpected_xtai_calendar_window_length")
    if expected_sessions[-1] != END_SESSION:
        raise RuntimeError("xtai_calendar_end_session_mismatch")

    prior_session = expected_sessions[0]
    audit_sessions = expected_sessions[1:]
    summary: dict[str, Any] = {
        "task": 89,
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "symbols": list(SYMBOLS),
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
        "calendar": "XTAI",
        "audit_session_count": AUDIT_SESSION_COUNT,
        "prior_session_for_first_overnight": prior_session.isoformat(),
        "first_audit_session": audit_sessions[0].isoformat(),
        "last_audit_session": audit_sessions[-1].isoformat(),
        "query_chunk_calendar_days": QUERY_CHUNK_CALENDAR_DAYS,
        "calendar_adjustments": [
            {
                "session_date": session_date.isoformat(),
                **details,
            }
            for session_date, details in sorted(AD_HOC_FULL_DAY_CLOSURES.items())
            if expected_sessions[0] <= session_date <= expected_sessions[-1]
        ],
        "symbols_result": [],
    }
    _write_summary(summary)

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )

        for symbol in SYMBOLS:
            contract = api.contracts.get(symbol)
            if contract is None:
                raise RuntimeError(f"shioaji_contract_not_found:{symbol}")

            symbol_result: dict[str, Any] = {
                "symbol": symbol,
                "query_chunks": [],
                "missing_expected_sessions": [],
                "extra_provider_sessions": [],
                "status": "fetching",
            }
            summary["symbols_result"].append(symbol_result)
            _write_summary(summary)

            provider_sessions = _fetch_symbol_sessions(
                api,
                contract,
                symbol,
                prior_session,
                END_SESSION,
                symbol_result,
                summary,
            )

            provider_dates = set(provider_sessions)
            expected_set = set(expected_sessions)
            missing = sorted(expected_set - provider_dates)
            extra = sorted(provider_dates - expected_set)
            symbol_result["missing_expected_sessions"] = [
                value.isoformat() for value in missing
            ]
            symbol_result["extra_provider_sessions"] = [
                value.isoformat() for value in extra
            ]
            if missing or extra:
                symbol_result["status"] = "session_coverage_failed"
                _write_summary(summary)
                raise RuntimeError(
                    f"session_coverage_mismatch:{symbol}:missing={len(missing)}:extra={len(extra)}"
                )

            shape_outliers = [
                diagnostic
                for session_date in expected_sessions
                if (
                    diagnostic := _session_shape_diagnostic(
                        provider_sessions[session_date],
                        session_date,
                    )
                )
                is not None
            ]
            symbol_result["minute_label_gap_diagnostics"] = shape_outliers
            symbol_result["sessions_with_missing_regular_labels"] = sum(
                bool(
                    [
                        label
                        for label in diagnostic["missing_labels_local"]
                        if label != "13:30"
                    ]
                )
                for diagnostic in shape_outliers
            )
            symbol_result["missing_regular_label_count"] = sum(
                len(
                    [
                        label
                        for label in diagnostic["missing_labels_local"]
                        if label != "13:30"
                    ]
                )
                for diagnostic in shape_outliers
            )
            symbol_result["sessions_missing_closing_auction_label"] = sum(
                "13:30" in diagnostic["missing_labels_local"]
                for diagnostic in shape_outliers
            )
            _write_summary(summary)

            security: SecurityIdentity = {
                "symbol": symbol,
                "exchange": "XTAI",
                "timezone": "Asia/Taipei",
                "calendar_id": "XTAI",
            }
            decoded: dict[date, tuple[Any, Any]] = {}
            for session_date in expected_sessions:
                decoded[session_date] = decode_shioaji_stock_kbars(
                    provider_sessions[session_date],
                    security,
                    session_date,
                    "as_printed",
                )

            measurements = []
            overnight_share_by_interval: dict[int, list[float]] = {
                5: [],
                10: [],
                15: [],
            }
            previous_closing = decoded[prior_session][1]

            for session_date in audit_sessions:
                bars, closing = decoded[session_date]
                overnight_log_return = calculate_overnight_log_return(
                    previous_closing["price"],
                    bars[0]["open"],
                )

                for interval in (5, 10, 15):
                    sampled = build_xtai_sampling_prices(bars, closing, interval)
                    intraday = (
                        calculate_intraday_realized_measures_from_sampled_prices(
                            sampled
                        )
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

                previous_closing = closing

            rows = build_measurement_audit_rows(measurements)
            audit_summary = summarize_measurement_audit(rows)
            if len(rows) != AUDIT_SESSION_COUNT:
                raise RuntimeError(
                    f"unexpected_measurement_audit_row_count:{symbol}:{len(rows)}"
                )

            ordered_outliers = sorted(
                rows,
                key=lambda row: max(
                    row["abs_log_gap_5m_10m"],
                    row["abs_log_gap_5m_15m"],
                ),
                reverse=True,
            )
            monotonic_5_10 = sum(
                row["whole_day_variance_5m"] > row["whole_day_variance_10m"]
                for row in rows
            )
            monotonic_10_15 = sum(
                row["whole_day_variance_10m"] > row["whole_day_variance_15m"]
                for row in rows
            )
            strict_descending = sum(
                row["whole_day_variance_5m"]
                > row["whole_day_variance_10m"]
                > row["whole_day_variance_15m"]
                for row in rows
            )

            symbol_result.update(
                {
                    "status": "accepted",
                    "provider_session_count": len(provider_sessions),
                    "audit_row_count": len(rows),
                    "measurement_audit_summary": _serialize_audit_summary(
                        audit_summary
                    ),
                    "monotonic_frequency": {
                        "rv_5m_gt_10m_pct": monotonic_5_10
                        / len(rows)
                        * 100.0,
                        "rv_10m_gt_15m_pct": monotonic_10_15
                        / len(rows)
                        * 100.0,
                        "rv_5m_gt_10m_gt_15m_pct": strict_descending
                        / len(rows)
                        * 100.0,
                    },
                    "overnight_variance_share": {
                        str(interval): {
                            "mean": statistics.fmean(values),
                            "median": statistics.median(values),
                            "max": max(values),
                        }
                        for interval, values in overnight_share_by_interval.items()
                    },
                    "top_abs_log_gap_sessions": [
                        {
                            "session_date": row["session_date"].isoformat(),
                            "whole_day_variance_5m": row[
                                "whole_day_variance_5m"
                            ],
                            "whole_day_variance_10m": row[
                                "whole_day_variance_10m"
                            ],
                            "whole_day_variance_15m": row[
                                "whole_day_variance_15m"
                            ],
                            "log_ratio_5m_10m": row["log_ratio_5m_10m"],
                            "log_ratio_5m_15m": row["log_ratio_5m_15m"],
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

        accepted_results = [
            result
            for result in summary["symbols_result"]
            if result.get("status") == "accepted"
        ]
        if len(accepted_results) != len(SYMBOLS):
            raise RuntimeError("not_all_symbols_accepted")

        summary["panel_median_metrics"] = _panel_median_metrics(
            accepted_results
        )
        summary["status"] = "accepted"
        _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass


def _fetch_symbol_sessions(
    api: sj.Shioaji,
    contract: Any,
    symbol: str,
    first_session: date,
    last_session: date,
    symbol_result: dict[str, Any],
    summary: dict[str, Any],
) -> dict[date, dict[str, list[int | float]]]:
    by_session: dict[date, dict[str, list[int | float]]] = {}
    cursor = first_session

    while cursor <= last_session:
        chunk_end = min(
            cursor + timedelta(days=QUERY_CHUNK_CALENDAR_DAYS - 1),
            last_session,
        )
        provider = api.kbars(
            contract=contract,
            start=cursor.isoformat(),
            end=chunk_end.isoformat(),
            timeout=15000,
        )
        normalized = _normalize_provider_payload(provider.dict())
        encoded = (
            json.dumps(
                {
                    "provider": "shioaji",
                    "provider_version": sj.__version__,
                    "symbol": symbol,
                    "start_date": cursor.isoformat(),
                    "end_date": chunk_end.isoformat(),
                    "payload": normalized,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

        symbol_result["query_chunks"].append(
            {
                "start_date": cursor.isoformat(),
                "end_date": chunk_end.isoformat(),
                "row_count": len(normalized["ts"]),
                "sdk_payload_sha256": sha256(encoded).hexdigest(),
            }
        )
        _merge_sessions(by_session, normalized)
        _write_summary(summary)

        cursor = chunk_end + timedelta(days=1)
        time_module.sleep(0.2)

    return by_session


def _normalize_provider_payload(payload: dict[str, Any]) -> dict[str, list[int | float]]:
    normalized: dict[str, list[int | float]] = {}
    for field in FIELDS:
        if field not in payload:
            if field == "Amount":
                continue
            raise RuntimeError(f"missing_shioaji_field:{field}")
        values = payload[field]
        if hasattr(values, "tolist"):
            values = values.tolist()
        if not isinstance(values, list):
            values = list(values)
        normalized[field] = [_number(value) for value in values]

    expected_count = len(normalized["ts"])
    if any(len(values) != expected_count for values in normalized.values()):
        raise RuntimeError("inconsistent_shioaji_chunk_lengths")
    return normalized


def _merge_sessions(
    by_session: dict[date, dict[str, list[int | float]]],
    payload: dict[str, list[int | float]],
) -> None:
    for index, raw_ts in enumerate(payload["ts"]):
        if not isinstance(raw_ts, int):
            raise RuntimeError("unexpected_shioaji_timestamp_type")
        seconds, nanoseconds = divmod(raw_ts, 1_000_000_000)
        if nanoseconds != 0:
            raise RuntimeError("unexpected_shioaji_timestamp_precision")
        session_date = datetime.fromtimestamp(
            seconds,
            tz=timezone.utc,
        ).date()

        target = by_session.setdefault(
            session_date,
            {field: [] for field in payload},
        )
        for field, values in payload.items():
            target[field].append(values[index])


def _session_shape_diagnostic(
    payload: dict[str, list[int | float]],
    session_date: date,
) -> dict[str, Any] | None:
    expected_labels = tuple(
        (
            datetime.combine(session_date, clock_time(9, 1))
            + timedelta(minutes=index)
        ).strftime("%H:%M")
        for index in range(265)
    ) + ("13:30",)

    observed_labels: list[str] = []
    wrong_date_labels: list[str] = []
    for raw_ts in payload["ts"]:
        if not isinstance(raw_ts, int):
            raise RuntimeError("unexpected_shioaji_timestamp_type")
        seconds, nanoseconds = divmod(raw_ts, 1_000_000_000)
        if nanoseconds != 0:
            raise RuntimeError("unexpected_shioaji_timestamp_precision")
        wall_clock = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
            tzinfo=None
        )
        if wall_clock.date() != session_date:
            wrong_date_labels.append(wall_clock.isoformat())
        else:
            observed_labels.append(wall_clock.strftime("%H:%M"))

    expected_set = set(expected_labels)
    observed_set = set(observed_labels)
    missing_labels = sorted(expected_set - observed_set)
    extra_labels = sorted(observed_set - expected_set)
    duplicate_count = len(observed_labels) - len(observed_set)

    if (
        len(observed_labels) == len(expected_labels)
        and not missing_labels
        and not extra_labels
        and duplicate_count == 0
        and not wrong_date_labels
    ):
        return None

    return {
        "session_date": session_date.isoformat(),
        "observed_provider_bar_count": len(observed_labels),
        "expected_provider_bar_count": len(expected_labels),
        "missing_labels_local": missing_labels,
        "extra_labels_local": extra_labels,
        "duplicate_label_count": duplicate_count,
        "wrong_date_labels": wrong_date_labels,
    }

def _serialize_audit_summary(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["security"] = dict(value["security"])
    result["first_session_date"] = value["first_session_date"].isoformat()
    result["last_session_date"] = value["last_session_date"].isoformat()
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


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _number(value: Any) -> int | float:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bool):
        raise RuntimeError("boolean_market_data_value")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and math.isfinite(value):
        return float(value)
    raise RuntimeError(f"invalid_market_data_number:{type(value).__name__}")


def _write_summary(summary: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
