from datetime import datetime, timedelta

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.provider_capture_manifest import ProviderCaptureManifest
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


def validate_provider_capture_sample(
    manifest: ProviderCaptureManifest,
    bars: tuple[CanonicalMinuteBar, ...],
) -> tuple[CanonicalMinuteBar, ...]:
    start = manifest["expected_session_start_utc"]
    end = manifest["expected_session_end_utc_exclusive"]

    if not _is_utc_datetime(start):
        raise InvalidProviderCaptureInputError("session_start_not_utc")
    if not _is_utc_datetime(end):
        raise InvalidProviderCaptureInputError("session_end_not_utc")
    if end <= start:
        raise InvalidProviderCaptureInputError("invalid_session_window")
    if manifest["expected_minute_count"] <= 0:
        raise InvalidProviderCaptureInputError("invalid_expected_minute_count")
    if not _is_sha256(manifest["raw_artifact_sha256"]):
        raise InvalidProviderCaptureInputError("invalid_artifact_sha256")
    if not bars:
        raise InvalidProviderCaptureInputError("empty_bars")
    if len(bars) != manifest["expected_minute_count"]:
        raise InvalidProviderCaptureInputError("unexpected_minute_count")

    previous_start: datetime | None = None
    for bar in bars:
        if bar["security"] != manifest["security"]:
            raise InvalidProviderCaptureInputError("mixed_security")
        if bar["session_date"] != manifest["session_date"]:
            raise InvalidProviderCaptureInputError("session_date_mismatch")
        if bar["price_basis"] != manifest["price_basis"]:
            raise InvalidProviderCaptureInputError("mixed_price_basis")

        bar_start = bar["bar_start_utc"]
        if not _is_utc_datetime(bar_start):
            raise InvalidProviderCaptureInputError("bar_start_not_utc")
        if not start <= bar_start < end:
            raise InvalidProviderCaptureInputError("bar_outside_session")
        if previous_start is not None and bar_start <= previous_start:
            raise InvalidProviderCaptureInputError("non_increasing_bar_starts")
        previous_start = bar_start

    return bars


def _is_utc_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)
