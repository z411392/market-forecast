from datetime import timedelta

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.provider_capture_acceptance_receipt import (
    ProviderCaptureAcceptanceReceipt,
)
from libs.market_data.dtos.provider_capture_manifest import ProviderCaptureManifest
from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.build_alpaca_historical_bars_request import (
    build_alpaca_historical_bars_request,
)
from libs.market_data.services.build_finmind_stock_kbar_request import (
    build_finmind_stock_kbar_request,
)
from libs.market_data.services.build_massive_minute_request import (
    build_massive_minute_request,
)
from libs.market_data.services.validate_provider_capture_sample import (
    validate_provider_capture_sample,
)


def build_provider_capture_acceptance_receipt(
    request: ProviderRequestSpec,
    manifest: ProviderCaptureManifest,
    bars: tuple[CanonicalMinuteBar, ...],
) -> ProviderCaptureAcceptanceReceipt:
    validated_bars = validate_provider_capture_sample(manifest, bars)
    expected_request = _build_expected_request(manifest)
    if request != expected_request:
        raise InvalidProviderCaptureInputError("request_spec_mismatch")

    gap_count = 0
    missing_grid_minutes = 0
    one_minute = timedelta(minutes=1)
    for previous, current in zip(
        validated_bars[:-1],
        validated_bars[1:],
        strict=True,
    ):
        delta = current["bar_start_utc"] - previous["bar_start_utc"]
        if delta > one_minute:
            gap_count += 1
            missing_grid_minutes += int(delta.total_seconds() // 60) - 1

    return {
        "provider": manifest["provider"],
        "source_symbol": manifest["source_symbol"],
        "security": manifest["security"],
        "session_date": manifest["session_date"],
        "retrieval_date": manifest["retrieval_date"],
        "request": request,
        "price_basis": manifest["price_basis"],
        "raw_artifact_sha256": manifest["raw_artifact_sha256"],
        "expected_minute_count": manifest["expected_minute_count"],
        "observed_minute_count": len(validated_bars),
        "first_bar_start_utc": validated_bars[0]["bar_start_utc"],
        "last_bar_start_utc": validated_bars[-1]["bar_start_utc"],
        "gap_count": gap_count,
        "missing_grid_minutes": missing_grid_minutes,
    }


def _build_expected_request(
    manifest: ProviderCaptureManifest,
) -> ProviderRequestSpec:
    if manifest["provider"] == "massive":
        return build_massive_minute_request(
            manifest["source_symbol"],
            manifest["session_date"],
        )
    if manifest["provider"] == "finmind":
        return build_finmind_stock_kbar_request(
            manifest["source_symbol"],
            manifest["session_date"],
        )
    if manifest["provider"] == "alpaca":
        return build_alpaca_historical_bars_request(
            source_symbol=manifest["source_symbol"],
            session_start_utc=manifest[
                "expected_session_start_utc"
            ],
            session_end_utc_exclusive=manifest[
                "expected_session_end_utc_exclusive"
            ],
            price_basis=manifest["price_basis"],
        )
    raise InvalidProviderCaptureInputError("unsupported_provider")
