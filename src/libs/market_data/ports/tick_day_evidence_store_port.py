from abc import ABC, abstractmethod

from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt


class TickDayEvidenceStorePort(ABC):
    @abstractmethod
    def contains(self, request_sha256: str) -> bool: ...

    @abstractmethod
    def load_receipt(
        self,
        request_sha256: str,
    ) -> TickDayEvidenceReceipt | None: ...

    @abstractmethod
    def __call__(
        self,
        sdk_observation: bytes,
        transaction_sequence: bytes,
        receipt: TickDayEvidenceReceipt,
    ) -> None: ...
