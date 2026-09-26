from typing import Literal, TypedDict

from libs.realized_variance.dtos.daily_realized_measures import DailyRealizedMeasures


class TransferPanelObservation(TypedDict):
    market: Literal["us", "taiwan"]
    measurement: DailyRealizedMeasures
