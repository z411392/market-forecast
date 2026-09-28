from abc import ABC, abstractmethod

from libs.market_data.dtos.provider_capture_acceptance_receipt import (
    ProviderCaptureAcceptanceReceipt,
)


class PersistProviderCaptureEvidencePort(ABC):
    @abstractmethod
    def __call__(
        self,
        raw_response: bytes,
        receipt: ProviderCaptureAcceptanceReceipt,
    ) -> None: ...
