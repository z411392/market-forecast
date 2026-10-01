from datetime import date, datetime
from typing import Literal

from libs.market_data.dtos.provider_capture_acceptance_receipt import (
    ProviderCaptureAcceptanceReceipt,
)
from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.ports.fetch_provider_raw_response_port import FetchProviderRawResponsePort
from libs.market_data.services.build_provider_capture_acceptance import (
    build_provider_capture_acceptance,
)


def execute_provider_capture_acceptance(
    fetch_raw_response: FetchProviderRawResponsePort,
    request: ProviderRequestSpec,
    provider: Literal["massive", "finmind", "alpaca"],
    source_symbol: str,
    retrieval_date: date,
    security: SecurityIdentity,
    session_date: date,
    expected_session_start_utc: datetime,
    expected_session_end_utc_exclusive: datetime,
    expected_minute_count: int,
    price_basis: Literal["as_printed", "split_adjusted"],
) -> ProviderCaptureAcceptanceReceipt:
    raw_response = fetch_raw_response(
        provider=provider,
        request=request,
    )
    return build_provider_capture_acceptance(
        request=request,
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
