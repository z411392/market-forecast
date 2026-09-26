from abc import ABC, abstractmethod

from libs.market_data.dtos.minute_bars_batch import MinuteBarsBatch
from libs.market_data.dtos.minute_bars_query import MinuteBarsQuery


class ReadMinuteBarsPort(ABC):
    @abstractmethod
    def __call__(self, query: MinuteBarsQuery) -> MinuteBarsBatch:
        raise NotImplementedError
