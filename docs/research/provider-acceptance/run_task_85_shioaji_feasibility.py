import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

import shioaji as sj


SESSIONS = ("2024-07-02", "2026-09-24")
OUTPUT_ROOT = Path("artifacts/private/provider-captures/task-85-shioaji")
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
TAIPEI = ZoneInfo("Asia/Taipei")


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


def _timestamp_local(value: object) -> datetime:
    numeric = _normalize_number(value)
    seconds = float(numeric)
    absolute = abs(seconds)
    if absolute >= 1e17:
        seconds /= 1_000_000_000
    elif absolute >= 1e14:
        seconds /= 1_000_000
    elif absolute >= 1e11:
        seconds /= 1_000

    wall_clock = datetime.fromtimestamp(seconds, timezone.utc).replace(tzinfo=None)
    return wall_clock.replace(tzinfo=TAIPEI)


def _reference_session_labels(session_date: str) -> tuple[datetime, ...]:
    local_date = date.fromisoformat(session_date)
    first = datetime.combine(local_date, time(9, 1), tzinfo=TAIPEI)
    continuous = tuple(first + timedelta(minutes=index) for index in range(265))
    closing_auction = datetime.combine(local_date, time(13, 30), tzinfo=TAIPEI)
    return (*continuous, closing_auction)


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

    records: list[dict[str, int | float]] = []
    for index in range(lengths["ts"]):
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

    observed_labels = tuple(_timestamp_local(record["ts"]) for record in records)
    expected_labels = _reference_session_labels(session_date)
    summary: dict[str, object] = {
        "session_date": session_date,
        "observed_provider_bar_count": len(records),
        "expected_reference_bar_count": len(expected_labels),
        "reference_session_structure_match": observed_labels == expected_labels,
        "closing_auction_gap_local": [
            f"{session_date}T13:26:00+08:00",
            f"{session_date}T13:27:00+08:00",
            f"{session_date}T13:28:00+08:00",
            f"{session_date}T13:29:00+08:00",
        ],
        "sdk_payload_sha256": sha256(encoded).hexdigest(),
        "timestamp_semantics": "provider_local_wall_clock_encoded_ns",
    }
    if records:
        first_local = observed_labels[0]
        last_local = observed_labels[-1]
        summary["first_ts_raw"] = records[0]["ts"]
        summary["last_ts_raw"] = records[-1]["ts"]
        summary["first_ts_local"] = first_local.isoformat()
        summary["last_ts_local"] = last_local.isoformat()
        summary["first_ts_utc"] = first_local.astimezone(timezone.utc).isoformat()
        summary["last_ts_utc"] = last_local.astimezone(timezone.utc).isoformat()

    return encoded, summary


def main() -> None:
    api_key = os.environ.get("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = os.environ.get("MARKET_FORECAST_SHIOAJI_SECRET_KEY")
    if api_key is None or not api_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_API_KEY")
    if secret_key is None or not secret_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    api_key = api_key.strip()
    secret_key = secret_key.strip()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "task": 85,
        "provider": "shioaji",
        "provider_version": sj.__version__,
        "symbol": "2330",
        "simulation": False,
        "subscribe_trade": False,
        "ca_activated": False,
        "session_structure_version": "xtai-normal-session-shioaji-v1",
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
            if not session_summary["reference_session_structure_match"]:
                raise RuntimeError(f"unexpected_shioaji_session_structure:{session_date}")

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
