import json
from datetime import date, timedelta
from pathlib import Path

from libs.realized_variance.domain.services.build_future_variance_targets import (
    build_future_variance_targets,
)

ROOT = Path("docs/research/provider-acceptance")
MANIFEST = ROOT / "cross-market-rv-measurement-target-manifest-v1.json"
TAIWAN = ROOT / "task-90-taiwan-canonical-measurement-decision.json"
US = ROOT / "task-98-us-canonical-measurement-decision.json"


def main() -> None:
    manifest = _load(MANIFEST)
    taiwan = _load(TAIWAN)
    us = _load(US)

    assert manifest["measurement_frozen"] is True
    assert manifest["forecast_score_used_for_measurement_selection"] is False

    us_manifest = manifest["markets"]["US"]
    tw_manifest = manifest["markets"]["Taiwan"]

    assert us_manifest["canonical_sampling_minutes"] == 5
    assert us_manifest["canonical_sampling_minutes"] == int(
        us["decision"]["us_canonical_sampling"].removesuffix("m")
    )
    assert us_manifest["price_basis"] == us["decision"]["price_basis"]
    assert us_manifest["algorithm_version"] == us["decision"]["algorithm_version"]
    assert us_manifest["measurement_decision"]["gate_passed"] is True

    assert tw_manifest["canonical_sampling_minutes"] == 15
    assert tw_manifest["canonical_sampling_minutes"] == int(
        taiwan["decision"]["taiwan_canonical_sampling"].removesuffix("m")
    )
    assert tw_manifest["algorithm_version"] == taiwan["decision"][
        "fixed_grid_algorithm_version"
    ]
    assert taiwan["decision"]["forecast_score_used"] is False
    assert taiwan["decision"]["rk_promoted_to_production_target"] is False

    target = manifest["target"]
    assert target["target_version"] == "whole_day_variance_v1"
    assert target["primary_horizon_sessions"] == 5
    assert target["confirmatory_horizon_sessions"] == 20
    assert target["origin_session_included"] is False
    assert target["first_target_session_offset"] == 1

    _verify_target_builder(
        sampling_minutes=5,
        price_basis="split_adjusted",
        algorithm_version="rv-core-v1",
        symbol="AAPL",
        horizon=5,
    )
    _verify_target_builder(
        sampling_minutes=5,
        price_basis="split_adjusted",
        algorithm_version="rv-core-v1",
        symbol="AAPL",
        horizon=20,
    )
    _verify_target_builder(
        sampling_minutes=15,
        price_basis="as_printed",
        algorithm_version="rv-core-v1+xtai-closing-auction-v4",
        symbol="2330",
        horizon=5,
    )
    _verify_target_builder(
        sampling_minutes=15,
        price_basis="as_printed",
        algorithm_version="rv-core-v1+xtai-closing-auction-v4",
        symbol="2330",
        horizon=20,
    )


def _verify_target_builder(
    *,
    sampling_minutes: int,
    price_basis: str,
    algorithm_version: str,
    symbol: str,
    horizon: int,
) -> None:
    dates = tuple(
        date(2026, 1, 1) + timedelta(days=index)
        for index in range(22)
    )
    security = {
        "symbol": symbol,
        "exchange": "XNAS" if symbol == "AAPL" else "XTAI",
        "timezone": (
            "America/New_York"
            if symbol == "AAPL"
            else "Asia/Taipei"
        ),
        "calendar_id": "XNAS" if symbol == "AAPL" else "XTAI",
    }
    measurements = tuple(
        {
            "security": security,
            "session_date": session_date,
            "sampling_minutes": sampling_minutes,
            "price_basis": price_basis,
            "regular_session_variance": float(index + 1),
            "overnight_log_return": 0.0,
            "overnight_variance": 0.0,
            "whole_day_variance": float(index + 1),
            "regular_positive_semivariance": float(index + 1),
            "regular_negative_semivariance": 0.0,
            "whole_day_positive_semivariance": float(index + 1),
            "whole_day_negative_semivariance": 0.0,
            "realized_quarticity": float(index + 1),
            "observation_count": 1,
            "algorithm_version": algorithm_version,
        }
        for index, session_date in enumerate(dates)
    )
    targets = build_future_variance_targets(
        measurements=measurements,
        session_dates=dates,
        horizon_sessions=horizon,
    )
    first = targets[0]
    assert first["origin_session_date"] == dates[0]
    assert first["first_target_session_date"] == dates[1]
    assert first["last_target_session_date"] == dates[horizon]
    assert first["realized_session_count"] == horizon
    assert first["target_version"] == "whole_day_variance_v1"
    assert first["sampling_minutes"] == sampling_minutes
    assert first["price_basis"] == price_basis
    assert first["algorithm_version"] == algorithm_version
    expected = sum(range(2, horizon + 2)) / horizon
    assert first["average_whole_day_variance"] == expected


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid_json_object:{path}")
    return value


if __name__ == "__main__":
    main()
