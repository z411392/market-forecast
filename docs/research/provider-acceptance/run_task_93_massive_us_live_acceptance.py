import json
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx

from libs.market_data.adapters.driven.filesystem_provider_capture_evidence_adapter import (
    FilesystemProviderCaptureEvidenceAdapter,
)
from libs.market_data.adapters.driven.httpx_provider_raw_response_adapter import (
    HttpxProviderRawResponseAdapter,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.build_massive_regular_session_minute_request import (
    build_massive_regular_session_minute_request,
)
from libs.market_data.services.execute_and_persist_provider_capture_acceptance import (
    execute_and_persist_provider_capture_acceptance,
)

OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-93-massive-us-live-acceptance"
)
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"

CASES = (
    {
        "role": "aapl_ordinary_as_printed",
        "symbol": "AAPL",
        "session_date": date(2024, 7, 2),
        "session_start_utc": datetime(
            2024, 7, 2, 13, 30, tzinfo=timezone.utc
        ),
        "session_end_utc_exclusive": datetime(
            2024, 7, 2, 20, 0, tzinfo=timezone.utc
        ),
        "expected_minute_count": 390,
        "price_basis": "as_printed",
    },
    {
        "role": "aapl_early_close_as_printed",
        "symbol": "AAPL",
        "session_date": date(2024, 7, 3),
        "session_start_utc": datetime(
            2024, 7, 3, 13, 30, tzinfo=timezone.utc
        ),
        "session_end_utc_exclusive": datetime(
            2024, 7, 3, 17, 0, tzinfo=timezone.utc
        ),
        "expected_minute_count": 210,
        "price_basis": "as_printed",
    },
    {
        "role": "nvda_pre_split_as_printed",
        "symbol": "NVDA",
        "session_date": date(2024, 6, 7),
        "session_start_utc": datetime(
            2024, 6, 7, 13, 30, tzinfo=timezone.utc
        ),
        "session_end_utc_exclusive": datetime(
            2024, 6, 7, 20, 0, tzinfo=timezone.utc
        ),
        "expected_minute_count": 390,
        "price_basis": "as_printed",
    },
    {
        "role": "nvda_post_split_as_printed",
        "symbol": "NVDA",
        "session_date": date(2024, 6, 10),
        "session_start_utc": datetime(
            2024, 6, 10, 13, 30, tzinfo=timezone.utc
        ),
        "session_end_utc_exclusive": datetime(
            2024, 6, 10, 20, 0, tzinfo=timezone.utc
        ),
        "expected_minute_count": 390,
        "price_basis": "as_printed",
    },
    {
        "role": "nvda_pre_split_adjusted",
        "symbol": "NVDA",
        "session_date": date(2024, 6, 7),
        "session_start_utc": datetime(
            2024, 6, 7, 13, 30, tzinfo=timezone.utc
        ),
        "session_end_utc_exclusive": datetime(
            2024, 6, 7, 20, 0, tzinfo=timezone.utc
        ),
        "expected_minute_count": 390,
        "price_basis": "split_adjusted",
    },
    {
        "role": "nvda_post_split_adjusted",
        "symbol": "NVDA",
        "session_date": date(2024, 6, 10),
        "session_start_utc": datetime(
            2024, 6, 10, 13, 30, tzinfo=timezone.utc
        ),
        "session_end_utc_exclusive": datetime(
            2024, 6, 10, 20, 0, tzinfo=timezone.utc
        ),
        "expected_minute_count": 390,
        "price_basis": "split_adjusted",
    },
)


def main() -> None:
    api_key = _required_secret("MARKET_FORECAST_MASSIVE_API_KEY")
    retrieval_date = datetime.now(timezone.utc).date()

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "task": 93,
        "provider": "massive",
        "base_url": "https://api.massive.com",
        "retrieval_date": retrieval_date.isoformat(),
        "status": "running",
        "cases": [],
    }
    _write_summary(summary)

    security_by_symbol = {
        symbol: _security(symbol)
        for symbol in ("AAPL", "NVDA")
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            fetch = HttpxProviderRawResponseAdapter(
                client=client,
                massive_base_url="https://api.massive.com",
                finmind_base_url="https://api.finmindtrade.com",
                massive_api_key=api_key,
                finmind_token=None,
                allow_live=True,
            )
            persist = FilesystemProviderCaptureEvidenceAdapter(
                EVIDENCE_ROOT
            )

            for case in CASES:
                symbol = str(case["symbol"])
                session_date = case["session_date"]
                start = case["session_start_utc"]
                end = case["session_end_utc_exclusive"]
                expected_count = int(
                    case["expected_minute_count"]
                )
                price_basis = case["price_basis"]
                if not isinstance(session_date, date):
                    raise RuntimeError("task93_invalid_session_date")
                if not isinstance(start, datetime):
                    raise RuntimeError("task93_invalid_session_start")
                if not isinstance(end, datetime):
                    raise RuntimeError("task93_invalid_session_end")
                if price_basis not in (
                    "as_printed",
                    "split_adjusted",
                ):
                    raise RuntimeError("task93_invalid_price_basis")

                typed_price_basis: Literal[
                    "as_printed", "split_adjusted"
                ] = price_basis

                request = build_massive_regular_session_minute_request(
                    source_symbol=symbol,
                    session_start_utc=start,
                    session_end_utc_exclusive=end,
                    price_basis=typed_price_basis,
                )
                receipt = (
                    execute_and_persist_provider_capture_acceptance(
                        fetch_raw_response=fetch,
                        persist_evidence=persist,
                        request=request,
                        provider="massive",
                        source_symbol=symbol,
                        retrieval_date=retrieval_date,
                        security=security_by_symbol[symbol],
                        session_date=session_date,
                        expected_session_start_utc=start,
                        expected_session_end_utc_exclusive=end,
                        expected_minute_count=expected_count,
                        price_basis=typed_price_basis,
                    )
                )
                summary["cases"].append(
                    {
                        "role": case["role"],
                        "receipt": _serialize_receipt(receipt),
                    }
                )
                _write_summary(summary)

        summary["status"] = "accepted"
        _write_summary(summary)
    except Exception as error:
        summary["status"] = "failed"
        summary["error_type"] = type(error).__name__
        _write_summary(summary)
        raise


def _security(symbol: str) -> SecurityIdentity:
    return {
        "symbol": symbol,
        "exchange": "XNAS",
        "timezone": "America/New_York",
        "calendar_id": "XNAS",
    }


def _serialize_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        json.dumps(
            receipt,
            default=_json_default,
            sort_keys=True,
        )
    )


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


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
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
