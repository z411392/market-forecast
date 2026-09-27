from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class MeasurementAuditRow(TypedDict):
    security: SecurityIdentity
    session_date: date
    price_basis: Literal["as_printed", "split_adjusted"]
    algorithm_version: str
    whole_day_variance_5m: float
    whole_day_variance_10m: float
    whole_day_variance_15m: float
    log_ratio_5m_10m: float
    log_ratio_5m_15m: float
    abs_log_gap_5m_10m: float
    abs_log_gap_5m_15m: float
    audit_version: Literal["rv_measurement_audit_v1"]
