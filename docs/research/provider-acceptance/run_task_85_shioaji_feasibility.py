import json
import math
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import shioaji as sj


SESSIONS = ("2024-07-02", "2026-09-24")
OUTPUT_ROOT = Path("artifacts/private/provider-captures/task-85-shioaji")
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"


def _as_list(value: object) -> list[object]:
    if hasattr(value, "tolist"):
        result = value.tolist()
        return result if isinstance(result, list) else [result]
    return list(value)  # type: ignore[arg-type]


def _normalize_number(value: object) -> int | float:
    if isinstance(value, bool):
        raise TypeError("boolean is not a valid market-data number")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite market-data number")
        return float(value)
    if hasattr(value, "item"):
        return _normalize_number(value.item())
    raise TypeError(f"unsupported market-data number: {type(value).__name__}")


def _timestamp_iso_utc(value: object) -> str:
    numeric = _normalize_number(value)
    seconds = float(numeric)
    absolute = abs(seconds)
    if absolute >= 1e17:
        seconds /= 1_000_000_000
    elif absolute >= 1e14:
        seconds /= 1_000_000
    elif absolute >= 1e11:
        seconds /= 1_000
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def _serialize_kbars(kbars: object, session_date: str) -> tuple[bytes, dict[str, object]]:
    fields = {
        "ts": _as_list(getattr(kbars, "ts")),
        "Open": _as_list(getattr(kbars, "Open")),
        "High": _as_list(getattr(kbars, "High")),
        "Low": _as_list(getattr(kbars, "Low")),
        "Close": _as_list(getattr(kbars, "Close")),
        "Volume": _as_list(getattr(kbars, "Volume")),
        "Amount": _as_list(getattr(kbars, "Amount")),
    }
    lengths = {name: len(values) for name, values in fields.items()}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"inconsistent Shioaji Kbars lengths: {lengths}")

    count = lengths["ts"]
    records: list[dict[str, int | float]] = []
    for index in range(count):
        records.append(
            {
                "ts": _normalize_number(fields["ts"][index]),
                "Open": _normalize_number(fields["Open"][index]),
                "High": _normalize_number(fields["High"][index]),
                "Low": _normalize_number(fields["Low"][index]),
                "Close": _normalize_number(fields["Close"][index]),
                "Volume": _normalize_number(fields["Volume"][index]),
                "Amount": _normalize_number(fields["Amount"][index]),
            }
        )

    payload = {
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "symbol": "2330",
        "session_date": session_date,
        "records": records,
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

    summary: dict[str, object] = {
        "session_date": session_date,
        "observed_minute_count": count,
        "expected_full_session_count": 270,
        "full_session_count_match": count == 270,
        "sdk_payload_sha256": sha256(encoded).hexdigest(),
    }
    if records:
        summary["first_ts_raw"] = records[0]["ts"]
        summary["last_ts_raw"] = records[-1]["ts"]
        summary["first_ts_utc"] = _timestamp_iso_utc(records[0]["ts"])
        summary["last_ts_utc"] = _timestamp_iso_utc(records[-1]["ts"])

    return encoded, summary


def main() -> None:
    api_key = os.environ.get("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = os.environ.get("MARKET_FORECAST_SHIOAJI_SECRET_KEY")
    if api_key is None or not api_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_API_KEY")
    if secret_key is None or not secret_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "task": 85,
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "symbol": "2330",
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "sessions": [],
    }

    api = sj.Shioaji(simulation=False)
    try:
        api.login(
            api_key=api_key,
            secret_key=secret_key,
            subscribe_trade=False,
        )
        contract = api.contracts.get("2330")
        if contract is None:
            raise RuntimeError("shioaji_contract_2330_not_found")

        for session_date in SESSIONS:
            kbars = api.kbars(
                contract=contract,
                start=session_date,
                end=session_date,
                timeout=15000,
            )
            payload, session_summary = _serialize_kbars(kbars, session_date)
            (OUTPUT_ROOT / f"2330-{session_date}.kbars.json").write_bytes(payload)
            summary["sessions"].append(session_summary)
            _write_summary(summary)
    finally:
        try:
            api.logout()
        except Exception:
            pass

    _write_summary(summary)


def _write_summary(summary: dict[str, object]) -> None:
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
