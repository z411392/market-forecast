from typing import TypedDict


class ProviderTrafficUsage(TypedDict):
    used_bytes: int
    limit_bytes: int
    remaining_bytes: int
