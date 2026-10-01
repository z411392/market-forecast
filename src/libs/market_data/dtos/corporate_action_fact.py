from datetime import date
from typing import Literal, NotRequired, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.source_provenance import SourceProvenance


class CorporateActionFact(TypedDict):
    security: SecurityIdentity
    action_type: Literal["split", "symbol_change", "cash_dividend", "other"]
    effective_date: date
    provenance: SourceProvenance
    ratio: NotRequired[float]
    previous_symbol: NotRequired[str]
    new_symbol: NotRequired[str]
    cash_amount: NotRequired[float]
    currency: NotRequired[str]
