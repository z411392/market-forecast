from datetime import date
from typing import get_args, get_origin, get_type_hints

from pytest import mark

from libs.forecast_transfer.dtos.transfer_panel_observation import (
    TransferPanelObservation,
)
from libs.forecast_transfer.dtos.unseen_symbol_fold import UnseenSymbolFold
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.dtos.daily_realized_measures import DailyRealizedMeasures


@mark.contract
def test_transfer_panel_contract() -> None:
    assert TransferPanelObservation.__required_keys__ == frozenset(
        {
            "market",
            "measurement",
        }
    )
    observation_hints = get_type_hints(TransferPanelObservation)
    assert get_args(observation_hints["market"]) == ("us", "taiwan")
    assert observation_hints["measurement"] is DailyRealizedMeasures

    assert UnseenSymbolFold.__required_keys__ == frozenset(
        {
            "fold_id",
            "train_us_securities",
            "train_taiwan_securities",
            "test_us_securities",
            "test_taiwan_securities",
            "train_end_session_date",
            "evaluation_start_session_date",
            "evaluation_end_session_date",
            "horizon_sessions",
            "purge_sessions",
        }
    )
    fold_hints = get_type_hints(UnseenSymbolFold)
    assert fold_hints["fold_id"] is int
    assert fold_hints["train_end_session_date"] is date
    assert fold_hints["evaluation_start_session_date"] is date
    assert fold_hints["evaluation_end_session_date"] is date
    assert get_args(fold_hints["horizon_sessions"]) == (5,)
    assert fold_hints["purge_sessions"] is int

    for field in (
        "train_us_securities",
        "train_taiwan_securities",
        "test_us_securities",
        "test_taiwan_securities",
    ):
        assert get_origin(fold_hints[field]) is tuple
        assert get_args(fold_hints[field]) == (SecurityIdentity, Ellipsis)
