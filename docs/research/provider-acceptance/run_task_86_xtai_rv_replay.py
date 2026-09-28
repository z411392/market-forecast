import json
import os
from datetime import date
from pathlib import Path

import shioaji as sj

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.decode_shioaji_stock_kbars import (
    decode_shioaji_stock_kbars,
)
from libs.realized_variance.domain.services.build_xtai_sampling_prices import (
    build_xtai_sampling_prices,
)
from libs.realized_variance.domain.services.calculate_intraday_realized_measures_from_sampled_prices import (
    calculate_intraday_realized_measures_from_sampled_prices,
)


SESSIONS = (date(2024, 7, 2), date(2026, 9, 24))
OUTPUT = Path("artifacts/private/provider-captures/task-86-xtai-rv/summary.json")


def main() -> None:
    api_key = os.environ.get("MARKET_FORECAST_SHIOAJI_API_KEY")
    secret_key = os.environ.get("MARKET_FORECAST_SHIOAJI_SECRET_KEY")
    if api_key is None or not api_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_API_KEY")
    if secret_key is None or not secret_key.strip():
        raise RuntimeError("missing MARKET_FORECAST_SHIOAJI_SECRET_KEY")

    security: SecurityIdentity = {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }

    summary: dict[str, object] = {
        "task": 86,
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
            api_key=api_key.strip(),
            secret_key=secret_key.strip(),
            subscribe_trade=False,
        )
        contract = api.contracts.get("2330")
        if contract is None:
            raise RuntimeError("shioaji_contract_2330_not_found")

        for session_date in SESSIONS:
            provider = api.kbars(
                contract=contract,
                start=session_date.isoformat(),
                end=session_date.isoformat(),
                timeout=15000,
            )
            payload = provider.dict()
            bars, closing = decode_shioaji_stock_kbars(
                payload,
                security,
                session_date,
                "as_printed",
            )
            interval_results: list[dict[str, object]] = []
            for interval in (5, 10, 15):
                sampled = build_xtai_sampling_prices(bars, closing, interval)
                measures = calculate_intraday_realized_measures_from_sampled_prices(
                    sampled
                )
                expected_observation_count = 270 // interval
                if measures["observation_count"] != expected_observation_count:
                    raise RuntimeError(
                        f"unexpected_observation_count:{session_date}:{interval}"
                    )
                interval_results.append(
                    {
                        "sampling_minutes": interval,
                        "sampled_price_count": len(sampled),
                        "observation_count": measures["observation_count"],
                        "regular_session_variance": measures["realized_variance"],
                        "realized_quarticity": measures["realized_quarticity"],
                        "positive_semivariance": measures["positive_semivariance"],
                        "negative_semivariance": measures["negative_semivariance"],
                        "algorithm_version": measures["algorithm_version"],
                    }
                )

            summary["sessions"].append(
                {
                    "session_date": session_date.isoformat(),
                    "provider_bar_count": len(payload["ts"]),
                    "observed_trade_bearing_minute_count": len(bars),
                    "closing_auction_at_utc": closing["matched_at_utc"].isoformat(),
                    "closing_auction_price": closing["price"],
                    "intervals": interval_results,
                }
            )
    finally:
        try:
            api.logout()
        except Exception:
            pass

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
