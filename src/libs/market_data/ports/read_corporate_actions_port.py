from abc import ABC, abstractmethod

from libs.market_data.dtos.corporate_action_fact import CorporateActionFact
from libs.market_data.dtos.corporate_actions_query import CorporateActionsQuery


class ReadCorporateActionsPort(ABC):
    @abstractmethod
    def __call__(self, query: CorporateActionsQuery) -> tuple[CorporateActionFact, ...]:
        raise NotImplementedError
