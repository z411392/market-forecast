from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class UnseenSymbolFold(TypedDict):
    fold_id: int
    train_us_securities: tuple[SecurityIdentity, ...]
    train_taiwan_securities: tuple[SecurityIdentity, ...]
    test_us_securities: tuple[SecurityIdentity, ...]
    test_taiwan_securities: tuple[SecurityIdentity, ...]
    train_end_session_date: date
    evaluation_start_session_date: date
    evaluation_end_session_date: date
    horizon_sessions: Literal[5]
    purge_sessions: int
