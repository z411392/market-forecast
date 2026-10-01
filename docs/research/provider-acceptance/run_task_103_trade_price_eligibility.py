import json
import math
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

SYMBOLS = ("AAPL", "NVDA")
SESSION_DATE = "2026-09-24"
EXPECTED_MINUTES = 390
PRICE_TOLERANCE = 1e-9

ELIGIBLE_CONDITIONS = frozenset(
    ("@", "A", "B", "D", "F", "K", "L", "O", "T", "X", "Y", "5", "6")
)
INELIGIBLE_CONDITIONS = frozenset(
    ("C", "G", "H", "I", "M", "N", "P", "Q", "R", "U", "V", "W", "Z", "4", "7", "9")
)
KNOWN_CONDITIONS = ELIGIBLE_CONDITIONS | INELIGIBLE_CONDITIONS

INPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-103-input"
)
TASK97_ROOT = INPUT_ROOT / "task97"
TASK102_ROOT = INPUT_ROOT / "task102"
OUTPUT_ROOT = Path(
    "artifacts/private/provider-captures/task-103-trade-price-eligibility"
)
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"


def main() -> None:
    results = [
        _validate_symbol(symbol)
        for symbol in SYMBOLS
    ]
    summary = {
        "task": 103,
        "session_date": SESSION_DATE,
        "status": "accepted",
        "price_rule": {
            "tape": "C",
            "bar_type": "minute",
            "strictest_condition_rule": True,
            "eligible_conditions": sorted(ELIGIBLE_CONDITIONS),
            "ineligible_conditions": sorted(INELIGIBLE_CONDITIONS),
            "unknown_condition_policy": "fail_closed",
        },
        "symbols": results,
        "ruling": {
            "transaction_price_eligibility_frozen": all(
                result["ohlc_mismatch_count"] == 0
                and result["reconstructed_minute_count"] == EXPECTED_MINUTES
                for result in results
            ),
            "provider_calls": 0,
            "rk_values_computed": False,
        },
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_symbol(symbol: str) -> dict[str, Any]:
    bars = _load_task97_bars(symbol)
    trades = _load_task102_trades(symbol)

    by_minute: dict[str, list[float]] = defaultdict(list)
    excluded_by_condition: Counter[str] = Counter()
    eligible_count = 0

    for trade in trades:
        conditions = trade.get("c")
        if not isinstance(conditions, list) or not conditions:
            raise RuntimeError(f"task103_missing_conditions:{symbol}")
        if any(not isinstance(value, str) for value in conditions):
            raise RuntimeError(f"task103_invalid_condition:{symbol}")

        unknown = set(conditions) - KNOWN_CONDITIONS
        if unknown:
            raise RuntimeError(
                f"task103_unknown_condition:{symbol}:{sorted(unknown)}"
            )

        price = trade.get("p")
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(float(price))
            or float(price) <= 0.0
        ):
            raise RuntimeError(f"task103_invalid_price:{symbol}")

        if all(condition in ELIGIBLE_CONDITIONS for condition in conditions):
            timestamp = trade.get("t")
            if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
                raise RuntimeError(f"task103_invalid_timestamp:{symbol}")
            minute = timestamp[:16] + ":00Z"
            by_minute[minute].append(float(price))
            eligible_count += 1
        else:
            for condition in conditions:
                if condition in INELIGIBLE_CONDITIONS:
                    excluded_by_condition[condition] += 1

    if len(by_minute) != EXPECTED_MINUTES:
        raise RuntimeError(
            f"task103_reconstructed_minute_count:{symbol}:{len(by_minute)}"
        )

    mismatches: list[dict[str, Any]] = []
    max_abs_difference = 0.0
    for bar in bars:
        timestamp = bar.get("t")
        if not isinstance(timestamp, str):
            raise RuntimeError(f"task103_invalid_bar_timestamp:{symbol}")
        minute = timestamp[:16] + ":00Z"
        prices = by_minute.get(minute)
        if not prices:
            raise RuntimeError(f"task103_missing_reconstructed_minute:{symbol}:{minute}")

        actual = {
            "o": prices[0],
            "h": max(prices),
            "l": min(prices),
            "c": prices[-1],
        }
        expected = {
            field: _finite_float(bar.get(field), symbol, field)
            for field in ("o", "h", "l", "c")
        }
        differences = {
            field: abs(actual[field] - expected[field])
            for field in ("o", "h", "l", "c")
        }
        minute_max = max(differences.values())
        max_abs_difference = max(max_abs_difference, minute_max)
        if minute_max > PRICE_TOLERANCE:
            mismatches.append(
                {
                    "minute": minute,
                    "actual": actual,
                    "expected": expected,
                    "differences": differences,
                }
            )

    if mismatches:
        raise RuntimeError(
            f"task103_ohlc_mismatch:{symbol}:{len(mismatches)}"
        )

    return {
        "symbol": symbol,
        "raw_trade_count": len(trades),
        "eligible_trade_count": eligible_count,
        "eligible_trade_fraction": eligible_count / len(trades),
        "excluded_trade_count": len(trades) - eligible_count,
        "reconstructed_minute_count": len(by_minute),
        "accepted_bar_count": len(bars),
        "ohlc_mismatch_count": len(mismatches),
        "max_abs_ohlc_difference": max_abs_difference,
        "excluded_condition_frequency": dict(
            excluded_by_condition.most_common()
        ),
    }


def _load_task97_bars(symbol: str) -> list[dict[str, Any]]:
    receipts = sorted(
        TASK97_ROOT.glob(
            f"evidence/alpaca/*/{SESSION_DATE}/*/*/acceptance-receipt.json"
        )
    )
    for receipt_path in receipts:
        receipt = _load_json(receipt_path)
        if receipt.get("source_symbol") != symbol:
            continue
        if receipt.get("price_basis") != "split_adjusted":
            continue
        if receipt.get("observed_minute_count") != EXPECTED_MINUTES:
            raise RuntimeError(f"task103_unexpected_bar_count:{symbol}")

        raw_path = receipt_path.parent / "raw-response.bin"
        raw_bytes = raw_path.read_bytes()
        if sha256(raw_bytes).hexdigest() != receipt.get("raw_artifact_sha256"):
            raise RuntimeError(f"task103_task97_raw_hash_mismatch:{symbol}")
        payload = json.loads(raw_bytes)
        if not isinstance(payload, dict) or payload.get("symbol") != symbol:
            raise RuntimeError(f"task103_task97_symbol_mismatch:{symbol}")
        bars = payload.get("bars")
        if not isinstance(bars, list) or len(bars) != EXPECTED_MINUTES:
            raise RuntimeError(f"task103_invalid_task97_bars:{symbol}")
        return bars
    raise RuntimeError(f"task103_task97_receipt_not_found:{symbol}")


def _load_task102_trades(symbol: str) -> list[dict[str, Any]]:
    page_paths = sorted(
        (TASK102_ROOT / "pages" / symbol).glob("page-*.json")
    )
    if not page_paths:
        raise RuntimeError(f"task103_task102_pages_not_found:{symbol}")

    trades: list[dict[str, Any]] = []
    for page_path in page_paths:
        payload = _load_json(page_path)
        if payload.get("symbol") != symbol:
            raise RuntimeError(f"task103_task102_symbol_mismatch:{symbol}")
        page_trades = payload.get("trades")
        if not isinstance(page_trades, list):
            raise RuntimeError(f"task103_invalid_task102_trades:{symbol}")
        for trade in page_trades:
            if not isinstance(trade, dict):
                raise RuntimeError(f"task103_invalid_trade_object:{symbol}")
            trades.append(trade)
    return trades


def _finite_float(
    value: object,
    symbol: str,
    field: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise RuntimeError(f"task103_invalid_bar_value:{symbol}:{field}")
    return float(value)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"task103_invalid_json_object:{path}")
    return value


if __name__ == "__main__":
    main()
