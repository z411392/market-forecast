import json
from hashlib import sha256

from pytest import mark

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec
from libs.market_data.services.build_provider_request_sha256 import (
    build_provider_request_sha256,
)


@mark.unit
def test_build_provider_request_sha256() -> None:
    request: ProviderRequestSpec = {
        "method": "GET",
        "path": "/v2/stocks/NVDA/bars",
        "query": (
            ("timeframe", "1Min"),
            ("adjustment", "raw"),
        ),
    }
    expected = sha256(
        json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert build_provider_request_sha256(request) == expected

    adjusted: ProviderRequestSpec = {
        **request,
        "query": (
            ("timeframe", "1Min"),
            ("adjustment", "split"),
        ),
    }
    assert build_provider_request_sha256(adjusted) != build_provider_request_sha256(request)
