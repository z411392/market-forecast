from datetime import date, datetime, time, timezone
from hashlib import sha256

from pytest import mark, raises

from libs.market_data.adapters.driven.filesystem_tick_day_evidence_adapter import (
    FilesystemTickDayEvidenceAdapter,
)
from libs.market_data.dtos.historical_tick_request_spec import HistoricalTickRequestSpec
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt
from libs.market_data.exceptions.provider_capture_evidence_conflict_error import (
    ProviderCaptureEvidenceConflictError,
)
from libs.market_data.exceptions.provider_capture_evidence_integrity_error import (
    ProviderCaptureEvidenceIntegrityError,
)


def _security() -> SecurityIdentity:
    return {
        "symbol": "2330",
        "exchange": "XTAI",
        "timezone": "Asia/Taipei",
        "calendar_id": "XTAI",
    }


def _request() -> HistoricalTickRequestSpec:
    return {
        "provider": "shioaji",
        "source_symbol": "2330",
        "session_date": date(2026, 9, 24),
        "query_type": "RangeTime",
        "time_start_local": time(9, 0),
        "time_end_local": time(13, 30, 59),
    }


def _receipt(
    *,
    request_sha256: str,
    sdk_sha256: str,
    transaction_sha256: str,
) -> TickDayEvidenceReceipt:
    return {
        "provider": "shioaji",
        "provider_version": "1.7.7",
        "source_symbol": "2330",
        "security": _security(),
        "session_date": date(2026, 9, 24),
        "request": _request(),
        "request_sha256": request_sha256,
        "sdk_observation_sha256": sdk_sha256,
        "transaction_sequence_sha256": transaction_sha256,
        "estimator_version": "tw-rk-parzen-trades-v1",
        "tick_count": 2,
        "first_observed_at_utc": datetime(
            2026,
            9,
            24,
            1,
            0,
            3,
            tzinfo=timezone.utc,
        ),
        "last_observed_at_utc": datetime(
            2026,
            9,
            24,
            5,
            30,
            0,
            tzinfo=timezone.utc,
        ),
        "opening_price": 2480.0,
        "closing_auction_observed_at_utc": datetime(
            2026,
            9,
            24,
            5,
            30,
            0,
            tzinfo=timezone.utc,
        ),
        "closing_auction_price": 2475.0,
        "duplicate_timestamp_adjacency_count": 0,
    }


@mark.unit
def test_filesystem_tick_day_evidence_adapter_is_resumable_and_immutable(
    tmp_path,
) -> None:
    sdk_observation = b'{"provider":"shioaji","rows":2}\n'
    transaction_sequence = b'{"transactions":[1,2]}\n'
    request_sha = "a" * 64
    receipt = _receipt(
        request_sha256=request_sha,
        sdk_sha256=sha256(sdk_observation).hexdigest(),
        transaction_sha256=sha256(transaction_sequence).hexdigest(),
    )

    adapter = FilesystemTickDayEvidenceAdapter(tmp_path)

    assert adapter.contains(request_sha) is False
    assert adapter.load_receipt(request_sha) is None

    adapter(sdk_observation, transaction_sequence, receipt)

    assert adapter.contains(request_sha) is True
    assert adapter.load_receipt(request_sha) == receipt

    evidence_dir = tmp_path / "shioaji" / request_sha
    assert (evidence_dir / "sdk-observation.json").read_bytes() == sdk_observation
    assert (evidence_dir / "transactions.json").read_bytes() == transaction_sequence
    assert (evidence_dir / "receipt.json").exists()

    adapter(sdk_observation, transaction_sequence, receipt)
    assert adapter.load_receipt(request_sha) == receipt

    with raises(ProviderCaptureEvidenceConflictError):
        adapter(
            b'{"provider":"shioaji","rows":3}\n',
            transaction_sequence,
            receipt,
        )


@mark.unit
def test_filesystem_tick_day_evidence_adapter_rejects_integrity_errors(
    tmp_path,
) -> None:
    sdk_observation = b'{"provider":"shioaji","rows":2}\n'
    transaction_sequence = b'{"transactions":[1,2]}\n'
    request_sha = "b" * 64
    receipt = _receipt(
        request_sha256=request_sha,
        sdk_sha256="0" * 64,
        transaction_sha256=sha256(transaction_sequence).hexdigest(),
    )

    adapter = FilesystemTickDayEvidenceAdapter(tmp_path)

    with raises(ProviderCaptureEvidenceIntegrityError):
        adapter(sdk_observation, transaction_sequence, receipt)

    with raises(ProviderCaptureEvidenceIntegrityError):
        adapter.contains("../not-a-digest")

    with raises(ProviderCaptureEvidenceIntegrityError):
        adapter.load_receipt("not-a-digest")
