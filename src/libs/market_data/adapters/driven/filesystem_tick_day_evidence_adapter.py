import json
import re
from datetime import date, datetime, time
from hashlib import sha256
from pathlib import Path
from libs.market_data.dtos.historical_tick_request_spec import (
    HistoricalTickRequestSpec,
)
from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.market_data.dtos.tick_day_evidence_receipt import TickDayEvidenceReceipt
from libs.market_data.exceptions.provider_capture_evidence_conflict_error import (
    ProviderCaptureEvidenceConflictError,
)
from libs.market_data.exceptions.provider_capture_evidence_integrity_error import (
    ProviderCaptureEvidenceIntegrityError,
)
from libs.market_data.services.build_historical_tick_request_sha256 import (
    build_historical_tick_request_sha256,
)


_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FilesystemTickDayEvidenceAdapter:
    def __init__(self, root: Path) -> None:
        self._root = root

    def contains(self, request_sha256: str) -> bool:
        evidence_dir = self._evidence_dir(request_sha256)
        return all(
            (evidence_dir / filename).is_file()
            for filename in (
                "sdk-observation.json",
                "transactions.json",
                "receipt.json",
            )
        )

    def load_receipt(
        self,
        request_sha256: str,
    ) -> TickDayEvidenceReceipt | None:
        evidence_dir = self._evidence_dir(request_sha256)
        receipt_path = evidence_dir / "receipt.json"
        if not receipt_path.is_file():
            return None

        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderCaptureEvidenceIntegrityError(
                "tick_day_evidence_invalid_receipt_json"
            ) from error
        return _deserialize_receipt(payload)

    def __call__(
        self,
        sdk_observation: bytes,
        transaction_sequence: bytes,
        receipt: TickDayEvidenceReceipt,
    ) -> None:
        _validate_bytes(
            sdk_observation,
            "tick_day_evidence_invalid_sdk_observation",
        )
        _validate_bytes(
            transaction_sequence,
            "tick_day_evidence_invalid_transaction_sequence",
        )

        request_sha256 = _validate_digest(receipt["request_sha256"])
        expected_request_sha = build_historical_tick_request_sha256(
            receipt["request"]
        )
        if request_sha256 != expected_request_sha:
            raise ProviderCaptureEvidenceIntegrityError(
                "tick_day_evidence_request_hash_mismatch"
            )
        if receipt["provider"] != "shioaji":
            raise ProviderCaptureEvidenceIntegrityError(
                "tick_day_evidence_invalid_provider"
            )
        if receipt["sdk_observation_sha256"] != sha256(
            sdk_observation
        ).hexdigest():
            raise ProviderCaptureEvidenceIntegrityError(
                "tick_day_evidence_sdk_hash_mismatch"
            )
        if receipt["transaction_sequence_sha256"] != sha256(
            transaction_sequence
        ).hexdigest():
            raise ProviderCaptureEvidenceIntegrityError(
                "tick_day_evidence_transaction_hash_mismatch"
            )

        evidence_dir = self._evidence_dir(request_sha256)
        evidence_dir.mkdir(parents=True, exist_ok=True)

        _write_immutable(
            evidence_dir / "sdk-observation.json",
            sdk_observation,
        )
        _write_immutable(
            evidence_dir / "transactions.json",
            transaction_sequence,
        )
        _write_immutable(
            evidence_dir / "receipt.json",
            _serialize_receipt(receipt),
        )

    def _evidence_dir(self, request_sha256: str) -> Path:
        digest = _validate_digest(request_sha256)
        return self._root / "shioaji" / digest


def _validate_bytes(value: object, error_code: str) -> None:
    if type(value) is not bytes or not value:
        raise ProviderCaptureEvidenceIntegrityError(error_code)


def _validate_digest(value: object) -> str:
    if not isinstance(value, str) or _DIGEST_PATTERN.fullmatch(value) is None:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_request_digest"
        )
    return value


def _serialize_receipt(receipt: TickDayEvidenceReceipt) -> bytes:
    request = receipt["request"]
    payload = {
        **receipt,
        "session_date": receipt["session_date"].isoformat(),
        "first_observed_at_utc": receipt["first_observed_at_utc"].isoformat(),
        "last_observed_at_utc": receipt["last_observed_at_utc"].isoformat(),
        "closing_auction_observed_at_utc": receipt[
            "closing_auction_observed_at_utc"
        ].isoformat(),
        "request": {
            **request,
            "session_date": request["session_date"].isoformat(),
            "time_start_local": request["time_start_local"].isoformat(),
            "time_end_local": request["time_end_local"].isoformat(),
        },
    }
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _deserialize_receipt(payload: object) -> TickDayEvidenceReceipt:
    if not isinstance(payload, dict):
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_shape"
        )

    try:
        provider = payload["provider"]
        provider_version = payload["provider_version"]
        source_symbol = payload["source_symbol"]
        security_payload = payload["security"]
        session_date_raw = payload["session_date"]
        request_payload = payload["request"]
        request_sha256 = payload["request_sha256"]
        sdk_sha256 = payload["sdk_observation_sha256"]
        transaction_sha256 = payload["transaction_sequence_sha256"]
        estimator_version = payload["estimator_version"]
        tick_count = payload["tick_count"]
        first_raw = payload["first_observed_at_utc"]
        last_raw = payload["last_observed_at_utc"]
        opening_price = payload["opening_price"]
        closing_raw = payload["closing_auction_observed_at_utc"]
        closing_price = payload["closing_auction_price"]
        duplicate_count = payload["duplicate_timestamp_adjacency_count"]
    except KeyError as error:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_receipt_missing_field"
        ) from error

    if provider != "shioaji":
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_provider"
        )
    if not isinstance(security_payload, dict):
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_security"
        )
    if not isinstance(request_payload, dict):
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_request"
        )

    security: SecurityIdentity = {
        "symbol": _require_str(security_payload.get("symbol")),
        "exchange": _require_str(security_payload.get("exchange")),
        "timezone": _require_str(security_payload.get("timezone")),
        "calendar_id": _require_str(security_payload.get("calendar_id")),
    }

    request_provider = request_payload.get("provider")
    request_query_type = request_payload.get("query_type")
    if request_provider != "shioaji" or request_query_type != "RangeTime":
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_request"
        )

    request: HistoricalTickRequestSpec = {
        "provider": "shioaji",
        "source_symbol": _require_str(request_payload.get("source_symbol")),
        "session_date": _parse_date(request_payload.get("session_date")),
        "query_type": "RangeTime",
        "time_start_local": _parse_time(
            request_payload.get("time_start_local")
        ),
        "time_end_local": _parse_time(request_payload.get("time_end_local")),
    }

    receipt: TickDayEvidenceReceipt = {
        "provider": "shioaji",
        "provider_version": _require_str(provider_version),
        "source_symbol": _require_str(source_symbol),
        "security": security,
        "session_date": _parse_date(session_date_raw),
        "request": request,
        "request_sha256": _validate_digest(request_sha256),
        "sdk_observation_sha256": _validate_digest(sdk_sha256),
        "transaction_sequence_sha256": _validate_digest(transaction_sha256),
        "estimator_version": _require_str(estimator_version),
        "tick_count": _require_nonnegative_int(tick_count),
        "first_observed_at_utc": _parse_datetime(first_raw),
        "last_observed_at_utc": _parse_datetime(last_raw),
        "opening_price": _require_float(opening_price),
        "closing_auction_observed_at_utc": _parse_datetime(closing_raw),
        "closing_auction_price": _require_float(closing_price),
        "duplicate_timestamp_adjacency_count": _require_nonnegative_int(
            duplicate_count
        ),
    }

    if build_historical_tick_request_sha256(request) != receipt[
        "request_sha256"
    ]:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_request_hash_mismatch"
        )
    return receipt


def _require_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_value"
        )
    return value


def _require_nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_value"
        )
    return value


def _require_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_value"
        )
    return float(value)


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_date"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_date"
        ) from error


def _parse_time(value: object) -> time:
    if not isinstance(value, str):
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_time"
        )
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_time"
        ) from error
    if parsed.tzinfo is not None:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_time"
        )
    return parsed


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_datetime"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_datetime"
        ) from error
    if parsed.tzinfo is None:
        raise ProviderCaptureEvidenceIntegrityError(
            "tick_day_evidence_invalid_receipt_datetime"
        )
    return parsed


def _write_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ProviderCaptureEvidenceConflictError(
                "tick_day_evidence_conflict"
            )
        return
    path.write_bytes(payload)
