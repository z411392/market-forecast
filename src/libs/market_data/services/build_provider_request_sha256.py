import json
from hashlib import sha256

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec


def build_provider_request_sha256(
    request: ProviderRequestSpec,
) -> str:
    payload = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()
