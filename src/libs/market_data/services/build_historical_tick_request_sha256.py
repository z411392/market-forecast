import json
from datetime import date, time
from hashlib import sha256

from libs.market_data.dtos.historical_tick_request_spec import HistoricalTickRequestSpec
from libs.market_data.exceptions.invalid_provider_capture_input_error import (
    InvalidProviderCaptureInputError,
)

_EXPECTED_START = time(9, 0)
_EXPECTED_END = time(13, 30, 59)


def build_historical_tick_request_sha256(
    request: HistoricalTickRequestSpec,
) -> str:
    try:
        provider = request["provider"]
        source_symbol = request["source_symbol"]
        session_date = request["session_date"]
        query_type = request["query_type"]
        time_start = request["time_start_local"]
        time_end = request["time_end_local"]
    except KeyError as error:
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_missing_field"
        ) from error

    if provider != "shioaji":
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_unsupported_provider"
        )
    if (
        not isinstance(source_symbol, str)
        or not source_symbol
        or source_symbol.strip() != source_symbol
    ):
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_invalid_source_symbol"
        )
    if type(session_date) is not date:
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_invalid_session_date"
        )
    if query_type != "RangeTime":
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_invalid_query_type"
        )
    if type(time_start) is not time or type(time_end) is not time:
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_invalid_time"
        )
    if time_start.tzinfo is not None or time_end.tzinfo is not None:
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_time_must_be_local_naive"
        )
    if time_start != _EXPECTED_START or time_end != _EXPECTED_END:
        raise InvalidProviderCaptureInputError(
            "historical_tick_request_window_mismatch"
        )

    payload = {
        "provider": provider,
        "query_type": query_type,
        "session_date": session_date.isoformat(),
        "source_symbol": source_symbol,
        "time_end_local": time_end.isoformat(),
        "time_start_local": time_start.isoformat(),
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
    return sha256(encoded).hexdigest()
