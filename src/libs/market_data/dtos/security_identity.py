from typing import TypedDict


class SecurityIdentity(TypedDict):
    symbol: str
    exchange: str
    timezone: str
    calendar_id: str
