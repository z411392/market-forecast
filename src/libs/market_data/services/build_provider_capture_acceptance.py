from datetime import date, datetime
from typing import Literal

from libs.market_data.dtos.provider_capture_acceptance_receipt import (
    ProviderCaptureAcceptanceReceipt,
)
from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.services.assemble_provider_capture_sample import (
    assemble_provider_capture_sample,
)
from libs.market_data.services.build_provider_capture_acceptance_receipt import (
    build_provider_capture_acceptance_receipt,
)


def build_provider_capture_acceptance(
    request: ProviderRequestSpec,
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
) -> ProviderCaptureAcceptanceReceipt:
    manifest, bars = assemble_provider_capture_sample(
        provider=provider,
        raw_response=raw_response,
        source_symbol=source_symbol,
        retrieval_date=retrieval_date,
        security=security,
        session_date=session_date,
        expected_session_start_utc=expected_session_start_utc,
        expected_session_end_utc_exclusive=expected_session_end_utc_exclusive,
        expected_minute_count=expected_minute_count,
        price_basis=price_basis,
    )
    return build_provider_capture_acceptance_receipt(
        request=request,
        manifest=manifest,
        bars=bars,
    )
