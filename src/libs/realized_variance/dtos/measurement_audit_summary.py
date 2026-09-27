from datetime import date
from typing import Literal, TypedDict

from libs.market_data.dtos.security_identity import SecurityIdentity


class MeasurementAuditSummary(TypedDict):
    security: SecurityIdentity
    price_basis: Literal["as_printed", "split_adjusted"]
    algorithm_version: str
    observation_count: int
    pearson_log_rv_5m_10m: float
    pearson_log_rv_5m_15m: float
    spearman_rv_5m_10m: float
    spearman_rv_5m_15m: float
    geometric_bias_5m_vs_10m_pct: float
    geometric_bias_5m_vs_15m_pct: float
    mean_abs_log_gap_5m_10m: float
    mean_abs_log_gap_5m_15m: float
    first_session_date: date
    last_session_date: date
    audit_version: Literal["rv_measurement_audit_v1"]
