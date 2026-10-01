import json
import math
import os
import statistics
import time
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import shioaji as sj

from libs.market_data.adapters.driven.shioaji_provider_traffic_usage_adapter import (
    ShioajiProviderTrafficUsageAdapter,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.decode_shioaji_stock_kbars import (
    decode_shioaji_stock_kbars,
)
from libs.realized_variance.constants.xtai_realized_variance_algorithm_version import (
    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
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

SYMBOLS = ("2330", "2317", "2454")
START_SESSION = date(2022, 7, 18)
END_SESSION = date(2026, 9, 24)
SAMPLING_MINUTES = 15
QUERY_CHUNK_CALENDAR_DAYS = 28
MIN_REMAINING_BYTES = 100 * 1024 * 1024
MAX_CURRENT_RUN_DELTA_BYTES = 250 * 1024 * 1024
FIELDS = ("ts", "Open", "High", "Low", "Close", "Volume", "Amount")

AD_HOC_FULL_DAY_CLOSURES = {
    date(2026, 7, 10): "typhoon_bavi_twse_full_day_closure",
}

OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-101-taiwan-canonical-panel"
)
CHUNK_ROOT = OUTPUT_ROOT / "chunks"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = _required_secret(
        "MARKET_FORECAST_SHIOAJI_SECRET_KEY"
    )

    calendar = xcals.get_calendar("XTAI")
    scheduled = tuple(
        value.date()
        for value in calendar.sessions_in_range(
            date(2022, 7, 1).isoformat(),
            END_SESSION.isoformat(),
        )
    )
    adjusted = tuple(
        value
        for value in scheduled
        if value not in AD_HOC_FULL_DAY_CLOSURES
    )
    if START_SESSION not in adjusted:
        raise RuntimeError("task101_tw_start_not_xtai_session")
    start_index = adjusted.index(START_SESSION)
    if start_index == 0:
        raise RuntimeError("task101_tw_missing_prior_session")

    prior_session = adjusted[start_index - 1]
    panel_sessions = adjusted[start_index:]
    expected_sessions = (prior_session, *panel_sessions)
    if panel_sessions[-1] != END_SESSION:
        raise RuntimeError("task101_tw_end_session_mismatch")

    summary: dict[str, Any] = {
        "task": 101,
        "slice": "S1-taiwan-canonical-panel",
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "price_basis": "as_printed",
        "calendar": "XTAI",
        "sampling_minutes": SAMPLING_MINUTES,
        "algorithm_version": XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION,
        "symbols": list(SYMBOLS),
        "prior_session_for_first_overnight": prior_session.isoformat(),
        "first_panel_session": panel_sessions[0].isoformat(),
        "last_panel_session": panel_sessions[-1].isoformat(),
        "panel_session_count": len(panel_sessions),
        "query_chunk_calendar_days": QUERY_CHUNK_CALENDAR_DAYS,
        "min_remaining_bytes": MIN_REMAINING_BYTES,
        "max_current_run_delta_bytes": MAX_CURRENT_RUN_DELTA_BYTES,
        "calendar_adjustments": [
            {
                "session_date": key.isoformat(),
                "reason": value,
            }
            for key, value in sorted(
                AD_HOC_FULL_DAY_CLOSURES.items()
            )
            if prior_session <= key <= END_SESSION
        ],
        "status": "running",
        "symbols_result": [],
    }
    _write_json(SUMMARY_PATH, summary)

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )
        usage_reader = ShioajiProviderTrafficUsageAdapter(api)
        initial_usage = usage_reader()
        summary["initial_usage"] = dict(initial_usage)
        _enforce_usage_guard(
            initial_usage,
            initial_usage["used_bytes"],
        )
        _write_json(SUMMARY_PATH, summary)

        all_daily: dict[str, list[dict[str, Any]]] = {}

        for symbol in SYMBOLS:
            contract = api.contracts.get(symbol)
            if contract is None:
                raise RuntimeError(
                    f"task101_shioaji_contract_missing:{symbol}"
                )

            symbol_result: dict[str, Any] = {
                "symbol": symbol,
                "status": "fetching",
                "query_chunks": [],
                "missing_expected_sessions": [],
                "extra_provider_sessions": [],
                "previous_tick_sample_count": 0,
                "previous_tick_session_count": 0,
                "max_previous_tick_staleness_upper_seconds": 0.0,
            }
            summary["symbols_result"].append(symbol_result)
            _write_json(SUMMARY_PATH, summary)

            provider_sessions, session_chunk_sha = (
                _fetch_symbol_sessions(
                    api=api,
                    usage_reader=usage_reader,
                    initial_used_bytes=initial_usage["used_bytes"],
                    contract=contract,
                    symbol=symbol,
                    first_session=prior_session,
                    last_session=END_SESSION,
                    symbol_result=symbol_result,
                    summary=summary,
                )
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
                _write_json(SUMMARY_PATH, summary)
                raise RuntimeError(
                    "task101_tw_session_coverage_mismatch:"
                    f"{symbol}:missing={len(missing)}:"
                    f"extra={len(extra)}"
                )

            security: SecurityIdentity = {
                "symbol": symbol,
                "exchange": "XTAI",
                "timezone": "Asia/Taipei",
                "calendar_id": "XTAI",
            }
            decoded: dict[date, tuple[Any, Any, Any]] = {}
            for session_date in expected_sessions:
                decoded[session_date] = decode_shioaji_stock_kbars(
                    provider_sessions[session_date],
                    security,
                    session_date,
                    "as_printed",
                )

            previous_closing = decoded[prior_session][2]
            rows: list[dict[str, Any]] = []
            previous_tick_sessions: set[date] = set()

            for session_date in panel_sessions:
                bars, session_open, closing = decoded[session_date]
                overnight = calculate_overnight_log_return(
                    previous_closing["price"],
                    session_open["price"],
                )
                sampled = build_xtai_sampling_prices(
                    bars,
                    session_open,
                    closing,
                    SAMPLING_MINUTES,
                )
                previous_tick = [
                    sample
                    for sample in sampled
                    if sample["observation_mode"] == "previous_tick"
                ]
                if previous_tick:
                    previous_tick_sessions.add(session_date)
                    symbol_result[
                        "previous_tick_sample_count"
                    ] += len(previous_tick)
                    symbol_result[
                        "max_previous_tick_staleness_upper_seconds"
                    ] = max(
                        symbol_result[
                            "max_previous_tick_staleness_upper_seconds"
                        ],
                        max(
                            sample[
                                "staleness_upper_bound_seconds"
                            ]
                            for sample in previous_tick
                        ),
                    )

                intraday = (
                    calculate_intraday_realized_measures_from_sampled_prices(
                        sampled,
                        session_open,
                    )
                )
                daily = calculate_daily_realized_measures(
                    intraday,
                    overnight,
                )
                rows.append(
                    {
                        "session_date": session_date.isoformat(),
                        "whole_day_variance": daily[
                            "whole_day_variance"
                        ],
                        "regular_session_variance": daily[
                            "regular_session_variance"
                        ],
                        "overnight_variance": daily[
                            "overnight_variance"
                        ],
                        "overnight_log_return": daily[
                            "overnight_log_return"
                        ],
                        "observation_count": daily[
                            "observation_count"
                        ],
                        "source_chunk_sha256": session_chunk_sha[
                            session_date
                        ],
                    }
                )
                previous_closing = closing

            symbol_result["previous_tick_session_count"] = len(
                previous_tick_sessions
            )
            symbol_result["provider_session_count"] = len(
                provider_sessions
            )
            symbol_result["accepted_panel_sessions"] = len(rows)
            symbol_result["status"] = "accepted"
            all_daily[symbol] = rows
            _write_json(SUMMARY_PATH, summary)

        final_usage = usage_reader()
        summary["final_usage"] = dict(final_usage)
        summary["current_run_delta_bytes"] = (
            final_usage["used_bytes"] - initial_usage["used_bytes"]
        )
        if summary["current_run_delta_bytes"] < 0:
            raise RuntimeError("task101_tw_decreasing_usage_counter")
        summary["status"] = "accepted"
        _write_json(SUMMARY_PATH, summary)
        _write_json(
            DAILY_PATH,
            {
                "artifact_version": (
                    "task-101-taiwan-canonical-panel-v1"
                ),
                "task": 101,
                "provider": "shioaji",
                "provider_version": sj.__version__,
                "calendar": "XTAI",
                "price_basis": "as_printed",
                "sampling_minutes": SAMPLING_MINUTES,
                "algorithm_version": (
                    XTAI_REALIZED_VARIANCE_ALGORITHM_VERSION
                ),
                "prior_session_for_first_overnight": (
                    prior_session.isoformat()
                ),
                "first_panel_session": (
                    panel_sessions[0].isoformat()
                ),
                "last_panel_session": (
                    panel_sessions[-1].isoformat()
                ),
                "panel_session_count": len(panel_sessions),
                "daily_values": all_daily,
            },
        )
    finally:
        try:
            api.logout()
        except Exception:
            pass


def _fetch_symbol_sessions(
    *,
    api: sj.Shioaji,
    usage_reader: ShioajiProviderTrafficUsageAdapter,
    initial_used_bytes: int,
    contract: Any,
    symbol: str,
    first_session: date,
    last_session: date,
    symbol_result: dict[str, Any],
    summary: dict[str, Any],
) -> tuple[
    dict[date, dict[str, list[int | float]]],
    dict[date, str],
]:
    by_session: dict[date, dict[str, list[int | float]]] = {}
    session_chunk_sha: dict[date, str] = {}
    cursor = first_session

    while cursor <= last_session:
        usage = usage_reader()
        _enforce_usage_guard(usage, initial_used_bytes)

        chunk_end = min(
            cursor
            + timedelta(days=QUERY_CHUNK_CALENDAR_DAYS - 1),
            last_session,
        )
        provider = api.kbars(
            contract=contract,
            start=cursor.isoformat(),
            end=chunk_end.isoformat(),
            timeout=15000,
        )
        normalized = _normalize_provider_payload(
            provider.dict()
        )
        payload = {
            "provider": "shioaji",
            "provider_version": sj.__version__,
            "symbol": symbol,
            "start_date": cursor.isoformat(),
            "end_date": chunk_end.isoformat(),
            "payload": normalized,
        }
        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        digest = sha256(encoded).hexdigest()

        path = (
            CHUNK_ROOT
            / symbol
            / f"{cursor.isoformat()}_{chunk_end.isoformat()}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)

        chunk_dates = _merge_sessions(
            by_session,
            normalized,
        )
        for session_date in chunk_dates:
            if session_date in session_chunk_sha:
                raise RuntimeError(
                    "task101_tw_session_in_multiple_chunks:"
                    f"{symbol}:{session_date}"
                )
            session_chunk_sha[session_date] = digest

        after = usage_reader()
        if after["used_bytes"] < usage["used_bytes"]:
            raise RuntimeError(
                "task101_tw_decreasing_usage_counter"
            )
        symbol_result["query_chunks"].append(
            {
                "start_date": cursor.isoformat(),
                "end_date": chunk_end.isoformat(),
                "row_count": len(normalized["ts"]),
                "chunk_sha256": digest,
                "usage_before": dict(usage),
                "usage_after": dict(after),
            }
        )
        summary["latest_usage"] = dict(after)
        _write_json(SUMMARY_PATH, summary)
        _enforce_usage_guard(after, initial_used_bytes)

        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.2)

    return by_session, session_chunk_sha


def _enforce_usage_guard(
    usage: dict[str, int],
    initial_used_bytes: int,
) -> None:
    if usage["remaining_bytes"] < MIN_REMAINING_BYTES:
        raise RuntimeError("task101_tw_remaining_traffic_guard")
    delta = usage["used_bytes"] - initial_used_bytes
    if delta < 0:
        raise RuntimeError("task101_tw_decreasing_usage_counter")
    if delta >= MAX_CURRENT_RUN_DELTA_BYTES:
        raise RuntimeError(
            "task101_tw_current_run_traffic_guard"
        )


def _normalize_provider_payload(
    payload: dict[str, Any],
) -> dict[str, list[int | float]]:
    normalized: dict[str, list[int | float]] = {}
    for field in FIELDS:
        if field not in payload:
            if field == "Amount":
                continue
            raise RuntimeError(
                f"task101_tw_missing_shioaji_field:{field}"
            )
        values = payload[field]
        if hasattr(values, "tolist"):
            values = values.tolist()
        if not isinstance(values, list):
            values = list(values)
        normalized[field] = [
            _number(value) for value in values
        ]

    expected_count = len(normalized["ts"])
    if any(
        len(values) != expected_count
        for values in normalized.values()
    ):
        raise RuntimeError(
            "task101_tw_inconsistent_chunk_lengths"
        )
    return normalized


def _merge_sessions(
    by_session: dict[date, dict[str, list[int | float]]],
    payload: dict[str, list[int | float]],
) -> set[date]:
    touched: set[date] = set()
    for index, raw_ts in enumerate(payload["ts"]):
        if not isinstance(raw_ts, int):
            raise RuntimeError(
                "task101_tw_unexpected_timestamp_type"
            )
        seconds, nanoseconds = divmod(
            raw_ts,
            1_000_000_000,
        )
        if nanoseconds != 0:
            raise RuntimeError(
                "task101_tw_unexpected_timestamp_precision"
            )
        session_date = datetime.fromtimestamp(
            seconds,
            tz=timezone.utc,
        ).date()
        touched.add(session_date)

        target = by_session.setdefault(
            session_date,
            {field: [] for field in payload},
        )
        for field, values in payload.items():
            target[field].append(values[index])
    return touched


def _number(value: Any) -> int | float:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bool):
        raise RuntimeError("task101_tw_boolean_market_value")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and math.isfinite(value):
        return float(value)
    raise RuntimeError(
        f"task101_tw_invalid_market_number:{type(value).__name__}"
    )


def _required_secret(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_{name}")
    return value.strip()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
