import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Literal, NoReturn

from libs.market_data.dtos.canonical_minute_bar import CanonicalMinuteBar
from libs.market_data.dtos.provider_capture_manifest import ProviderCaptureManifest
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)
from libs.market_data.services.decode_alpaca_stock_bars import (
    decode_alpaca_stock_bars,
)
from libs.market_data.services.decode_finmind_stock_kbar import decode_finmind_stock_kbar
from libs.market_data.services.decode_massive_minute_aggregates import (
    decode_massive_minute_aggregates,
)
from libs.market_data.services.validate_provider_capture_sample import (
    validate_provider_capture_sample,
)


def assemble_provider_capture_sample(
    provider: Literal["massive", "finmind", "alpaca"],
    raw_response: bytes,
    source_symbol: str,
    retrieval_date: date,
    security: SecurityIdentity,
    session_date: date,
    expected_session_start_utc: datetime,
    expected_session_end_utc_exclusive: datetime,
    expected_minute_count: int,
    price_basis: Literal["as_printed", "split_adjusted"],
) -> tuple[ProviderCaptureManifest, tuple[CanonicalMinuteBar, ...]]:
    if type(raw_response) is not bytes:
        raise InvalidProviderCaptureInputError("raw_response_not_bytes")
    if not raw_response:
        raise InvalidProviderCaptureInputError("raw_response_empty")
    if type(retrieval_date) is not date:
        raise InvalidProviderCaptureInputError("retrieval_date_not_plain_date")
    if type(session_date) is not date:
        raise InvalidProviderCaptureInputError("session_date_not_plain_date")

    raw_artifact_sha256 = hashlib.sha256(raw_response).hexdigest()
    try:
        payload = json.loads(raw_response, parse_constant=_reject_non_json_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        raise InvalidProviderCaptureInputError("raw_response_invalid_json") from error

    if not isinstance(payload, Mapping):
        raise InvalidProviderCaptureInputError("raw_response_not_object")

    if provider == "massive":
        bars = decode_massive_minute_aggregates(
            payload=payload,
            expected_source_symbol=source_symbol,
            security=security,
        )
    elif provider == "finmind":
        bars = decode_finmind_stock_kbar(
            payload=payload,
            expected_source_symbol=source_symbol,
            security=security,
        )
    elif provider == "alpaca":
        bars = decode_alpaca_stock_bars(
            payload=payload,
            expected_source_symbol=source_symbol,
            security=security,
            price_basis=price_basis,
        )
    else:
        raise InvalidProviderCaptureInputError("unsupported_provider")

    manifest: ProviderCaptureManifest = {
        "provider": provider,
        "source_symbol": source_symbol,
        "retrieval_date": retrieval_date,
        "security": security,
        "session_date": session_date,
        "expected_session_start_utc": expected_session_start_utc,
        "expected_session_end_utc_exclusive": expected_session_end_utc_exclusive,
        "expected_minute_count": expected_minute_count,
        "price_basis": price_basis,
        "raw_artifact_sha256": raw_artifact_sha256,
    }
    validated_bars = validate_provider_capture_sample(manifest, bars)
    return manifest, validated_bars


def _reject_non_json_constant(value: str) -> NoReturn:
    raise ValueError(value)
