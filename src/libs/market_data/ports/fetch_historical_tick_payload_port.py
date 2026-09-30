from abc import ABC, abstractmethod
from collections.abc import Mapping

from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)


class FetchHistoricalTickPayloadPort(ABC):
    @abstractmethod
    def __call__(
        self,
        request: HistoricalTickRequestSpec,
    ) -> Mapping[str, object]: ...
