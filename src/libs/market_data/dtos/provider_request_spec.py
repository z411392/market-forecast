from typing import Literal, TypedDict


class ProviderRequestSpec(TypedDict):
    method: Literal["GET"]
    path: str
    query: tuple[tuple[str, str], ...]
