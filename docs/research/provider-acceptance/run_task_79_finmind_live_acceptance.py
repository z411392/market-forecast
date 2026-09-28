import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from libs.market_data.adapters.driven.filesystem_provider_capture_evidence_adapter import (
    FilesystemProviderCaptureEvidenceAdapter,
)
from libs.market_data.adapters.driven.httpx_provider_raw_response_adapter import (
    HttpxProviderRawResponseAdapter,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.build_finmind_stock_kbar_request import (
    build_finmind_stock_kbar_request,
)
from libs.market_data.services.execute_and_persist_provider_capture_acceptance import (
    execute_and_persist_provider_capture_acceptance,
)


_SESSIONS = (date(2024, 7, 2), date(2026, 9, 24))
_OUTPUT_ROOT = Path("artifacts/private/provider-captures/task-79")
_SUMMARY_PATH = _OUTPUT_ROOT / "summary.json"


def main() -> None:
    token = os.environ.get("MARKET_FORECAST_FINMIND_TOKEN")
    if token is None or not token.strip():
        raise RuntimeError("missing MARKET_FORECAST_FINMIND_TOKEN")

    _OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "task": 79,
        "provider": "finmind",
        "dataset": "TaiwanStockKBar",
        "source_symbol": "2330",
        "sessions": [],
    }

    security: SecurityIdentity = {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }
    retrieval_date = datetime.now(timezone.utc).date()

    with httpx.Client(timeout=30.0) as client:
        fetch = HttpxProviderRawResponseAdapter(
            client=client,
            massive_base_url="https://api.massive.com",
            finmind_base_url="https://api.finmindtrade.com",
            massive_api_key=None,
            finmind_token=token,
            allow_live=True,
        )
        persist = FilesystemProviderCaptureEvidenceAdapter(_OUTPUT_ROOT)

        for session_date in _SESSIONS:
            try:
                receipt = execute_and_persist_provider_capture_acceptance(
                    fetch_raw_response=fetch,
                    persist_evidence=persist,
                    request=build_finmind_stock_kbar_request("2330", session_date),
                    provider="finmind",
                    source_symbol="2330",
                    retrieval_date=retrieval_date,
                    security=security,
                    session_date=session_date,
                    expected_session_start_utc=datetime(
                        session_date.year,
                        session_date.month,
                        session_date.day,
                        1,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    expected_session_end_utc_exclusive=datetime(
                        session_date.year,
                        session_date.month,
                        session_date.day,
                        5,
                        30,
                        tzinfo=timezone.utc,
                    ),
                    expected_minute_count=270,
                    price_basis="as_printed",
                )
            except Exception as error:
                summary["sessions"].append(
                    {
                        "session_date": session_date.isoformat(),
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
                _write_summary(summary)
                raise

            summary["sessions"].append(
                {
                    "session_date": session_date.isoformat(),
                    "status": "accepted",
                    "raw_artifact_sha256": receipt["raw_artifact_sha256"],
                    "observed_minute_count": receipt["observed_minute_count"],
                    "gap_count": receipt["gap_count"],
                    "missing_grid_minutes": receipt["missing_grid_minutes"],
                    "first_bar_start_utc": receipt["first_bar_start_utc"].isoformat(),
                    "last_bar_start_utc": receipt["last_bar_start_utc"].isoformat(),
                }
            )
            _write_summary(summary)

    _write_summary(summary)


def _write_summary(summary: dict[str, object]) -> None:
    _SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
