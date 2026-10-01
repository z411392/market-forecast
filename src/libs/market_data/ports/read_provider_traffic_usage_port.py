from abc import ABC, abstractmethod

from libs.market_data.dtos.provider_traffic_usage import ProviderTrafficUsage


class ReadProviderTrafficUsagePort(ABC):
    @abstractmethod
    def __call__(self) -> ProviderTrafficUsage: ...
