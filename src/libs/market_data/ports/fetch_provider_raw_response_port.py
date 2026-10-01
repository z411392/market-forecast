from abc import ABC, abstractmethod
from typing import Literal

from libs.market_data.dtos.provider_request_spec import ProviderRequestSpec


class FetchProviderRawResponsePort(ABC):
    @abstractmethod
    def __call__(
        self,
        provider: Literal["massive", "finmind", "alpaca"],
        request: ProviderRequestSpec,
    ) -> bytes: ...
