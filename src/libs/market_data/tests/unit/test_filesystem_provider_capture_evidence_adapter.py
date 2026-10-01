import json
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path

from pytest import mark, raises

from libs.market_data.adapters.driven.filesystem_provider_capture_evidence_adapter import (
    FilesystemProviderCaptureEvidenceAdapter,
)
from libs.market_data.exceptions.provider_capture_evidence_conflict_error import (
    ProviderCaptureEvidenceConflictError,
)
from libs.market_data.exceptions.provider_capture_evidence_integrity_error import (
    ProviderCaptureEvidenceIntegrityError,
)
from libs.market_data.services.build_provider_request_sha256 import (
    build_provider_request_sha256,
)


def _receipt(raw_response: bytes) -> dict[str, object]:
    return {
        "provider": "massive",
        "source_symbol": "AAPL",
        "security": {
            "symbol": "AAPL",
            "exchange": "XNAS",
            "timezone": "America/New_York",
            "calendar_id": "XNYS",
        },
        "session_date": date(2024, 7, 2),
        "retrieval_date": date(2024, 7, 3),
        "request": {
            "method": "GET",
            "path": "/v2/aggs/ticker/AAPL/range/1/minute/2024-07-02/2024-07-02",
            "query": (
                ("adjusted", "false"),
                ("sort", "asc"),
                ("limit", "50000"),
            ),
        },
        "price_basis": "as_printed",
        "raw_artifact_sha256": sha256(raw_response).hexdigest(),
        "expected_minute_count": 390,
        "observed_minute_count": 390,
        "first_bar_start_utc": datetime(2024, 7, 2, 13, 30, tzinfo=timezone.utc),
        "last_bar_start_utc": datetime(2024, 7, 2, 19, 59, tzinfo=timezone.utc),
        "gap_count": 0,
        "missing_grid_minutes": 0,
    }


@mark.unit
def test_filesystem_provider_capture_evidence_adapter(tmp_path: Path) -> None:
    raw_response = b'{"status":"OK","results":[]}'
    receipt = _receipt(raw_response)
    digest = sha256(raw_response).hexdigest()
    request_digest = build_provider_request_sha256(
        receipt["request"]  # type: ignore[arg-type]
    )
    adapter = FilesystemProviderCaptureEvidenceAdapter(root=tmp_path)

    adapter(raw_response=raw_response, receipt=receipt)

    evidence_dir = tmp_path / "massive" / "2024-07-03" / "2024-07-02" / request_digest / digest
    raw_path = evidence_dir / "raw-response.bin"
    receipt_path = evidence_dir / "acceptance-receipt.json"

    assert raw_path.read_bytes() == raw_response
    receipt_bytes = receipt_path.read_bytes()
    assert receipt_bytes.endswith(b"\n")
    receipt_payload = json.loads(receipt_bytes)
    assert receipt_payload["provider"] == "massive"
    assert receipt_payload["source_symbol"] == "AAPL"
    assert receipt_payload["session_date"] == "2024-07-02"
    assert receipt_payload["retrieval_date"] == "2024-07-03"
    assert receipt_payload["first_bar_start_utc"] == "2024-07-02T13:30:00+00:00"
    assert receipt_payload["last_bar_start_utc"] == "2024-07-02T19:59:00+00:00"
    assert receipt_payload["request"]["query"] == [
        ["adjusted", "false"],
        ["sort", "asc"],
        ["limit", "50000"],
    ]
    assert "AAPL" not in evidence_dir.parts

    adapter(raw_response=raw_response, receipt=receipt)
    assert raw_path.read_bytes() == raw_response
    assert receipt_path.read_bytes() == receipt_bytes

    split_receipt = dict(receipt)
    split_receipt["request"] = {
        **receipt["request"],  # type: ignore[dict-item]
        "query": (
            ("adjusted", "true"),
            ("sort", "asc"),
            ("limit", "50000"),
        ),
    }
    split_receipt["price_basis"] = "split_adjusted"
    adapter(
        raw_response=raw_response,
        receipt=split_receipt,  # type: ignore[arg-type]
    )
    split_request_digest = build_provider_request_sha256(
        split_receipt["request"]  # type: ignore[arg-type]
    )
    split_dir = tmp_path / "massive" / "2024-07-03" / "2024-07-02" / split_request_digest / digest
    assert split_dir != evidence_dir
    assert (split_dir / "raw-response.bin").read_bytes() == raw_response

    mismatched = dict(receipt)
    mismatched["raw_artifact_sha256"] = "0" * 64
    with raises(
        ProviderCaptureEvidenceIntegrityError,
        match="provider_capture_evidence_hash_mismatch",
    ):
        adapter(raw_response=raw_response, receipt=mismatched)
    assert not (tmp_path / "massive" / "2024-07-03" / "2024-07-02" / request_digest / ("0" * 64)).exists()

    raw_path.write_bytes(b"tampered")
    with raises(
        ProviderCaptureEvidenceConflictError,
        match="provider_capture_evidence_conflict",
    ):
        adapter(raw_response=raw_response, receipt=receipt)
    assert raw_path.read_bytes() == b"tampered"

    other_root = tmp_path / "receipt-conflict"
    other = FilesystemProviderCaptureEvidenceAdapter(root=other_root)
    other(raw_response=raw_response, receipt=receipt)
    other_receipt = (
        other_root
        / "massive"
        / "2024-07-03"
        / "2024-07-02"
        / request_digest
        / digest
        / "acceptance-receipt.json"
    )
    other_receipt.write_bytes(b"{}\n")
    with raises(
        ProviderCaptureEvidenceConflictError,
        match="provider_capture_evidence_conflict",
    ):
        other(raw_response=raw_response, receipt=receipt)
    assert other_receipt.read_bytes() == b"{}\n"
