import json
import math
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx

from libs.market_data.adapters.driven.filesystem_provider_capture_evidence_adapter import (
    FilesystemProviderCaptureEvidenceAdapter,
)
from libs.market_data.adapters.driven.httpx_alpaca_provider_raw_response_adapter import (
    HttpxAlpacaProviderRawResponseAdapter,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.build_alpaca_historical_bars_request import (
    build_alpaca_historical_bars_request,
)
from libs.market_data.services.build_provider_request_sha256 import (
    build_provider_request_sha256,
)
from libs.market_data.services.execute_and_persist_provider_capture_acceptance import (
    execute_and_persist_provider_capture_acceptance,
)

OUTPUT_ROOT = Path("artifacts/private/provider-captures/task-95-alpaca-us-live-acceptance")
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"

CASES = (
    (
        "AAPL",
        date(2024, 7, 2),
        "2024-07-02T13:30:00+00:00",
        "2024-07-02T20:00:00+00:00",
        390,
        "as_printed",
        "aapl_ordinary_raw",
    ),
    (
        "AAPL",
        date(2024, 7, 3),
        "2024-07-03T13:30:00+00:00",
        "2024-07-03T17:00:00+00:00",
        210,
        "as_printed",
        "aapl_early_close_raw",
    ),
    (
        "NVDA",
        date(2024, 6, 7),
        "2024-06-07T13:30:00+00:00",
        "2024-06-07T20:00:00+00:00",
        390,
        "as_printed",
        "nvda_pre_split_raw",
    ),
    (
        "NVDA",
        date(2024, 6, 10),
        "2024-06-10T13:30:00+00:00",
        "2024-06-10T20:00:00+00:00",
        390,
        "as_printed",
        "nvda_post_split_raw",
    ),
    (
        "NVDA",
        date(2024, 6, 7),
        "2024-06-07T13:30:00+00:00",
        "2024-06-07T20:00:00+00:00",
        390,
        "split_adjusted",
        "nvda_pre_split_adjusted",
    ),
    (
        "NVDA",
        date(2024, 6, 10),
        "2024-06-10T13:30:00+00:00",
        "2024-06-10T20:00:00+00:00",
        390,
        "split_adjusted",
        "nvda_post_split_adjusted",
    ),
)


def main() -> None:
    key_id = _required("MARKET_FORECAST_ALPACA_API_KEY_ID")
    secret = _required("MARKET_FORECAST_ALPACA_SECRET_KEY")
    retrieval_date = datetime.now(timezone.utc).date()

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "task": 95,
        "provider": "alpaca",
        "feed": "sip",
        "retrieval_date": retrieval_date.isoformat(),
        "status": "running",
        "cases": [],
    }
    _write_summary(summary)

    securities = {symbol: _security(symbol) for symbol in ("AAPL", "NVDA")}

    with httpx.Client(timeout=30.0) as client:
        fetch = HttpxAlpacaProviderRawResponseAdapter(
            client=client,
            api_key_id=key_id,
            secret_key=secret,
            allow_live=True,
        )
        persist = FilesystemProviderCaptureEvidenceAdapter(EVIDENCE_ROOT)

        for (
            symbol,
            session_date,
            start_text,
            end_text,
            expected_count,
            price_basis,
            role,
        ) in CASES:
            start = datetime.fromisoformat(start_text)
            end = datetime.fromisoformat(end_text)
            typed_basis: Literal["as_printed", "split_adjusted"] = price_basis  # type: ignore[assignment]
            request = build_alpaca_historical_bars_request(
                source_symbol=symbol,
                session_start_utc=start,
                session_end_utc_exclusive=end,
                price_basis=typed_basis,
            )
            receipt = execute_and_persist_provider_capture_acceptance(
                fetch_raw_response=fetch,
                persist_evidence=persist,
                request=request,
                provider="alpaca",
                source_symbol=symbol,
                retrieval_date=retrieval_date,
                security=securities[symbol],
                session_date=session_date,
                expected_session_start_utc=start,
                expected_session_end_utc_exclusive=end,
                expected_minute_count=expected_count,
                price_basis=typed_basis,
            )
            request_digest = build_provider_request_sha256(receipt["request"])
            raw_path = (
                EVIDENCE_ROOT
                / "alpaca"
                / retrieval_date.isoformat()
                / session_date.isoformat()
                / request_digest
                / receipt["raw_artifact_sha256"]
                / "raw-response.bin"
            )
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
            bars = payload["bars"]
            if not isinstance(bars, list) or not bars:
                raise RuntimeError("task95_missing_persisted_bars")
            summary["cases"].append(
                {
                    "role": role,
                    "symbol": symbol,
                    "session_date": session_date.isoformat(),
                    "price_basis": typed_basis,
                    "observed_minute_count": receipt["observed_minute_count"],
                    "gap_count": receipt["gap_count"],
                    "missing_grid_minutes": receipt["missing_grid_minutes"],
                    "raw_artifact_sha256": receipt["raw_artifact_sha256"],
                    "first_bar_start_utc": receipt["first_bar_start_utc"].isoformat(),
                    "last_bar_start_utc": receipt["last_bar_start_utc"].isoformat(),
                    "first_open": float(bars[0]["o"]),
                    "last_close": float(bars[-1]["c"]),
                }
            )
            _write_summary(summary)

    by_role = {case["role"]: case for case in summary["cases"]}
    pre_ratio = by_role["nvda_pre_split_raw"]["last_close"] / by_role["nvda_pre_split_adjusted"]["last_close"]
    post_ratio = (
        by_role["nvda_post_split_raw"]["first_open"] / by_role["nvda_post_split_adjusted"]["first_open"]
    )
    if not math.isclose(
        pre_ratio,
        10.0,
        rel_tol=0.02,
        abs_tol=0.0,
    ):
        raise RuntimeError(f"task95_unexpected_pre_split_ratio:{pre_ratio}")
    if not math.isclose(
        post_ratio,
        1.0,
        rel_tol=0.02,
        abs_tol=0.0,
    ):
        raise RuntimeError(f"task95_unexpected_post_split_ratio:{post_ratio}")

    summary["split_semantics"] = {
        "pre_split_raw_to_adjusted_close_ratio": pre_ratio,
        "post_split_raw_to_adjusted_open_ratio": post_ratio,
        "expected_pre_split_ratio": 10.0,
        "expected_post_split_ratio": 1.0,
        "status": "accepted",
    }
    summary["status"] = "accepted"
    _write_summary(summary)


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _required(name: str) -> str:
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
