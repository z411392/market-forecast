import json
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from libs.market_data.dtos.provider_capture_acceptance_receipt import (
    ProviderCaptureAcceptanceReceipt,
)
from libs.market_data.exceptions.provider_capture_evidence_conflict_error import (
    ProviderCaptureEvidenceConflictError,
)
from libs.market_data.exceptions.provider_capture_evidence_integrity_error import (
    ProviderCaptureEvidenceIntegrityError,
)
from libs.market_data.ports.persist_provider_capture_evidence_port import (
    PersistProviderCaptureEvidencePort,
)


class FilesystemProviderCaptureEvidenceAdapter(PersistProviderCaptureEvidencePort):
    def __init__(self, root: Path) -> None:
        self._root = root

    def __call__(
        self,
        raw_response: bytes,
        receipt: ProviderCaptureAcceptanceReceipt,
    ) -> None:
        _validate_raw_response(raw_response)
        provider = _validate_provider(receipt["provider"])
        retrieval_date = _validate_plain_date(
            receipt["retrieval_date"],
            "provider_capture_evidence_invalid_retrieval_date",
        )
        session_date = _validate_plain_date(
            receipt["session_date"],
            "provider_capture_evidence_invalid_session_date",
        )

        digest = sha256(raw_response).hexdigest()
        if receipt["raw_artifact_sha256"] != digest:
            raise ProviderCaptureEvidenceIntegrityError(
                "provider_capture_evidence_hash_mismatch"
            )

        evidence_dir = (
            self._root
            / provider
            / retrieval_date.isoformat()
            / session_date.isoformat()
            / digest
        )
        evidence_dir.mkdir(parents=True, exist_ok=True)

        _write_immutable(
            evidence_dir / "raw-response.bin",
            raw_response,
        )
        _write_immutable(
            evidence_dir / "acceptance-receipt.json",
            _serialize_receipt(receipt),
        )


def _validate_raw_response(raw_response: bytes) -> None:
    if type(raw_response) is not bytes or not raw_response:
        raise ProviderCaptureEvidenceIntegrityError(
            "provider_capture_evidence_invalid_raw_response"
        )


def _validate_provider(
    provider: str,
) -> Literal["massive", "finmind", "alpaca"]:
    if provider == "massive":
        return "massive"
    if provider == "finmind":
        return "finmind"
    if provider == "alpaca":
        return "alpaca"
    raise ProviderCaptureEvidenceIntegrityError(
        "provider_capture_evidence_invalid_provider"
    )


def _validate_plain_date(value: object, error_type: str) -> date:
    if type(value) is not date:
        raise ProviderCaptureEvidenceIntegrityError(error_type)
    return value


def _serialize_receipt(
    receipt: ProviderCaptureAcceptanceReceipt,
) -> bytes:
    payload = json.dumps(
        receipt,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (payload + "\n").encode("utf-8")


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"unsupported receipt JSON type: {type(value).__name__}")


def _write_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ProviderCaptureEvidenceConflictError(
                "provider_capture_evidence_conflict"
            )
        return
    path.write_bytes(payload)
