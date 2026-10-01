import json
import os
import time
from datetime import date, datetime, timedelta, timezone
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
from libs.market_data.services.decode_alpaca_stock_bars import (
    decode_alpaca_stock_bars,
)
from libs.realized_variance.domain.services.aggregate_minute_bars import (
    aggregate_minute_bars,
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

SYMBOLS = ("GOOGL", "NVDA", "QQQ", "TSM")
START_SESSION = date(2022, 7, 18)
END_SESSION = date(2026, 9, 24)
SAMPLING_MINUTES = 5
REQUEST_SLEEP_SECONDS = 0.36

OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-101-us-canonical-panel"
)
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
DAILY_PATH = OUTPUT_ROOT / "daily-values.json"


def main() -> None:
    key_id = _required_secret("MARKET_FORECAST_ALPACA_API_KEY_ID")
    secret_key = _required_secret("MARKET_FORECAST_ALPACA_SECRET_KEY")
    retrieval_date = datetime.now(timezone.utc).date()

    calendar = xcals.get_calendar("XNAS")
    wide_sessions = tuple(
        value.date()
        for value in calendar.sessions_in_range(
            date(2022, 7, 1).isoformat(),
            END_SESSION.isoformat(),
        )
    )
    if START_SESSION not in wide_sessions:
        raise RuntimeError("task101_us_start_not_xnas_session")
    start_index = wide_sessions.index(START_SESSION)
    if start_index == 0:
        raise RuntimeError("task101_us_missing_prior_session")

    prior_session = wide_sessions[start_index - 1]
    audit_sessions = wide_sessions[start_index:]
    expected_sessions = (prior_session, *audit_sessions)
    if audit_sessions[-1] != END_SESSION:
        raise RuntimeError("task101_us_end_session_mismatch")

    securities = {
        symbol: _security(symbol)
        for symbol in SYMBOLS
    }
    persist = FilesystemProviderCaptureEvidenceAdapter(
        EVIDENCE_ROOT
    )
    previous_close: dict[str, float] = {}
    daily_rows: dict[str, list[dict[str, Any]]] = {
        symbol: [] for symbol in SYMBOLS
    }

    summary: dict[str, Any] = {
        "task": 101,
        "slice": "S1-us-canonical-panel",
        "provider": "alpaca",
        "feed": "sip",
        "source_timeframe": "1Min",
        "price_basis": "split_adjusted",
        "calendar": "XNAS",
        "sampling_minutes": SAMPLING_MINUTES,
        "algorithm_version": "rv-core-v1",
        "symbols": list(SYMBOLS),
        "prior_session_for_first_overnight": prior_session.isoformat(),
        "prior_anchor_rule": "final_regular_minute_only",
        "first_panel_session": audit_sessions[0].isoformat(),
        "last_panel_session": audit_sessions[-1].isoformat(),
        "panel_session_count": len(audit_sessions),
        "retrieval_date": retrieval_date.isoformat(),
        "request_sleep_seconds": REQUEST_SLEEP_SECONDS,
        "status": "running",
        "symbol_progress": {
            symbol: {
                "accepted_source_sessions": 0,
                "accepted_panel_sessions": 0,
                "missing_grid_minutes": 0,
                "gap_count": 0,
                "cache_hits": 0,
                "provider_fetches": 0,
            }
            for symbol in SYMBOLS
        },
    }
    _write_json(SUMMARY_PATH, summary)

    with httpx.Client(timeout=45.0) as client:
        fetch = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id=key_id,
            secret_key=secret_key,
            allow_live=True,
        )

        for session_index, session_date in enumerate(
            expected_sessions
        ):
            label = session_date.isoformat()
            session_open = calendar.session_open(label).to_pydatetime()
            session_close = calendar.session_close(label).to_pydatetime()
            full_session_minute_count = int(
                (session_close - session_open).total_seconds() // 60
            )
            if full_session_minute_count not in (210, 390):
                raise RuntimeError(
                    "task101_us_unexpected_session_minutes:"
                    f"{label}:{full_session_minute_count}"
                )

            is_prior_anchor = session_index == 0
            request_start = (
                session_close - timedelta(minutes=1)
                if is_prior_anchor
                else session_open
            )
            expected_minute_count = (
                1 if is_prior_anchor else full_session_minute_count
            )

            for symbol in SYMBOLS:
                request = build_alpaca_historical_bars_request(
                    source_symbol=symbol,
                    session_start_utc=request_start,
                    session_end_utc_exclusive=session_close,
                    price_basis="split_adjusted",
                )
                raw = _load_cached_raw(
                    session_date=session_date,
                    request=request,
                )
                progress = summary["symbol_progress"][symbol]
                if raw is None:
                    raw = fetch(provider="alpaca", request=request)
                    progress["provider_fetches"] += 1
                    time.sleep(REQUEST_SLEEP_SECONDS)
                else:
                    progress["cache_hits"] += 1

                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise RuntimeError("task101_us_response_not_object")
                preview = decode_alpaca_stock_bars(
                    payload=payload,
                    expected_source_symbol=symbol,
                    security=securities[symbol],
                    price_basis="split_adjusted",
                )
                expected_starts = {
                    request_start + timedelta(minutes=index)
                    for index in range(expected_minute_count)
                }
                observed_starts = {
                    bar["bar_start_utc"] for bar in preview
                }
                missing_starts = sorted(
                    expected_starts - observed_starts
                )
                incomplete_panel_session = (
                    not is_prior_anchor
                    and len(preview) != expected_minute_count
                )

                if len(preview) != expected_minute_count:
                    diagnostic = {
                        "symbol": symbol,
                        "session_date": session_date.isoformat(),
                        "role": (
                            "prior_anchor"
                            if is_prior_anchor
                            else "panel_session"
                        ),
                        "expected_minute_count": expected_minute_count,
                        "observed_minute_count": len(preview),
                        "first_observed_utc": (
                            preview[0]["bar_start_utc"].isoformat()
                            if preview
                            else None
                        ),
                        "last_observed_utc": (
                            preview[-1]["bar_start_utc"].isoformat()
                            if preview
                            else None
                        ),
                        "missing_minute_starts_utc": [
                            value.isoformat()
                            for value in missing_starts
                        ],
                        "request_sha256": (
                            build_provider_request_sha256(request)
                        ),
                        "raw_artifact_sha256": __import__(
                            "hashlib"
                        ).sha256(raw).hexdigest(),
                    }
                    summary.setdefault(
                        "incomplete_source_sessions",
                        [],
                    ).append(diagnostic)
                    _write_diagnostic_raw(
                        symbol=symbol,
                        session_date=session_date,
                        request=request,
                        raw=raw,
                    )

                    if is_prior_anchor:
                        raise RuntimeError(
                            "task101_us_prior_anchor_incomplete:"
                            f"{symbol}:{label}:"
                            f"{len(preview)}/{expected_minute_count}"
                        )
                    if not preview:
                        raise RuntimeError(
                            "task101_us_empty_panel_session:"
                            f"{symbol}:{label}"
                        )
                    if (
                        preview[0]["bar_start_utc"] != session_open
                        or preview[-1]["bar_start_utc"]
                        != session_close - timedelta(minutes=1)
                    ):
                        raise RuntimeError(
                            "task101_us_missing_open_or_close_anchor:"
                            f"{symbol}:{label}"
                        )

                if incomplete_panel_session:
                    progress["accepted_source_sessions"] += 1
                    progress.setdefault(
                        "incomplete_panel_sessions",
                        0,
                    )
                    progress["incomplete_panel_sessions"] += 1

                    overnight = calculate_overnight_log_return(
                        previous_close[symbol],
                        preview[0]["open"],
                    )
                    daily_rows[symbol].append(
                        {
                            "session_date": session_date.isoformat(),
                            "whole_day_variance": None,
                            "regular_session_variance": None,
                            "overnight_variance": (
                                overnight * overnight
                            ),
                            "overnight_log_return": overnight,
                            "observation_count": 0,
                            "request_sha256": (
                                build_provider_request_sha256(request)
                            ),
                            "raw_artifact_sha256": __import__(
                                "hashlib"
                            ).sha256(raw).hexdigest(),
                            "missing_reason": (
                                "incomplete_regular_session_sip_minutes"
                            ),
                            "missing_minute_starts_utc": [
                                value.isoformat()
                                for value in missing_starts
                            ],
                        }
                    )
                    progress["accepted_panel_sessions"] += 1
                    progress["missing_grid_minutes"] += len(
                        missing_starts
                    )
                    previous_close[symbol] = preview[-1]["close"]
                    _write_json(SUMMARY_PATH, summary)
                    continue

                manifest, bars = assemble_provider_capture_sample(
                    provider="alpaca",
                    raw_response=raw,
                    source_symbol=symbol,
                    retrieval_date=retrieval_date,
                    security=securities[symbol],
                    session_date=session_date,
                    expected_session_start_utc=request_start,
                    expected_session_end_utc_exclusive=session_close,
                    expected_minute_count=expected_minute_count,
                    price_basis="split_adjusted",
                )
                receipt = build_provider_capture_acceptance_receipt(
                    request=request,
                    manifest=manifest,
                    bars=bars,
                )
                persist(raw_response=raw, receipt=receipt)

                progress["accepted_source_sessions"] += 1
                progress["missing_grid_minutes"] += receipt[
                    "missing_grid_minutes"
                ]
                progress["gap_count"] += receipt["gap_count"]

                if session_index == 0:
                    previous_close[symbol] = bars[-1]["close"]
                else:
                    overnight = calculate_overnight_log_return(
                        previous_close[symbol],
                        bars[0]["open"],
                    )
                    aggregated = aggregate_minute_bars(
                        bars,
                        SAMPLING_MINUTES,
                        session_open,
                    )
                    intraday = calculate_intraday_realized_measures(
                        aggregated
                    )
                    daily = calculate_daily_realized_measures(
                        intraday,
                        overnight,
                    )
                    daily_rows[symbol].append(
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
                            "request_sha256": (
                                build_provider_request_sha256(request)
                            ),
                            "raw_artifact_sha256": receipt[
                                "raw_artifact_sha256"
                            ],
                        }
                    )
                    progress["accepted_panel_sessions"] += 1
                    previous_close[symbol] = bars[-1]["close"]

                _write_json(SUMMARY_PATH, summary)

    for symbol in SYMBOLS:
        rows = daily_rows[symbol]
        if len(rows) != len(audit_sessions):
            raise RuntimeError(
                f"task101_us_panel_count_mismatch:{symbol}:{len(rows)}"
            )
        if summary["symbol_progress"][symbol]["gap_count"] != 0:
            raise RuntimeError(f"task101_us_gap_count:{symbol}")

    summary["status"] = "accepted"
    _write_json(SUMMARY_PATH, summary)
    _write_json(
        DAILY_PATH,
        {
            "artifact_version": "task-101-us-canonical-panel-v1",
            "task": 101,
            "provider": "alpaca",
            "feed": "sip",
            "calendar": "XNAS",
            "price_basis": "split_adjusted",
            "sampling_minutes": SAMPLING_MINUTES,
            "algorithm_version": "rv-core-v1",
            "prior_session_for_first_overnight": (
                prior_session.isoformat()
            ),
            "first_panel_session": audit_sessions[0].isoformat(),
            "last_panel_session": audit_sessions[-1].isoformat(),
            "panel_session_count": len(audit_sessions),
            "daily_values": daily_rows,
        },
    )




def _write_diagnostic_raw(
    *,
    symbol: str,
    session_date: date,
    request: dict[str, Any],
    raw: bytes,
) -> None:
    import hashlib

    request_sha = build_provider_request_sha256(request)
    raw_sha = hashlib.sha256(raw).hexdigest()
    path = (
        OUTPUT_ROOT
        / "diagnostics"
        / symbol
        / session_date.isoformat()
        / request_sha
        / f"{raw_sha}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)

def _load_cached_raw(
    *,
    session_date: date,
    request: dict[str, Any],
) -> bytes | None:
    request_sha = build_provider_request_sha256(request)
    pattern = (
        EVIDENCE_ROOT
        / "alpaca"
        / "*"
        / session_date.isoformat()
        / request_sha
        / "*"
        / "raw-response.bin"
    )
    paths = sorted(Path().glob(str(pattern)))
    if not paths:
        return None

    payloads = {path.read_bytes() for path in paths}
    if len(payloads) != 1:
        raise RuntimeError(
            "task101_us_conflicting_cached_raw_response"
        )
    return next(iter(payloads))

def _security(symbol: str) -> SecurityIdentity:
    exchange = "XNYS" if symbol == "TSM" else "XNAS"
    return {
        "symbol": symbol,
        "exchange": exchange,
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


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
