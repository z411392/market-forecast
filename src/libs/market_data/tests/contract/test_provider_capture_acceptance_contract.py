from datetime import date, datetime
from typing import get_args, get_type_hints

from pytest import mark

from libs.market_data.dtos.provider_capture_manifest import ProviderCaptureManifest
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)


@mark.contract
def test_provider_capture_acceptance_contract() -> None:
    assert ProviderCaptureManifest.__required_keys__ == frozenset(
        {
            "provider",
            "source_symbol",
            "retrieval_date",
            "security",
            "session_date",
            "expected_session_start_utc",
            "expected_session_end_utc_exclusive",
            "expected_minute_count",
            "price_basis",
            "raw_artifact_sha256",
        }
    )
    hints = get_type_hints(ProviderCaptureManifest)
    assert get_args(hints["provider"]) == ("massive", "finmind")
    assert hints["source_symbol"] is str
    assert hints["retrieval_date"] is date
    assert hints["security"] is SecurityIdentity
    assert hints["session_date"] is date
    assert hints["expected_session_start_utc"] is datetime
    assert hints["expected_session_end_utc_exclusive"] is datetime
    assert hints["expected_minute_count"] is int
    assert get_args(hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert hints["raw_artifact_sha256"] is str

    assert issubclass(InvalidProviderCaptureInputError, ValueError)
    assert InvalidProviderCaptureInputError.type == "invalid_provider_capture_input"
