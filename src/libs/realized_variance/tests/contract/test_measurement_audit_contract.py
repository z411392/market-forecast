from datetime import date
from typing import get_args, get_type_hints

from libs.market_data.dtos.security_identity import SecurityIdentity
from libs.realized_variance.dtos.measurement_audit_row import MeasurementAuditRow
from libs.realized_variance.dtos.measurement_audit_summary import MeasurementAuditSummary
from pytest import mark


@mark.contract
def test_measurement_audit_contract() -> None:
    assert MeasurementAuditRow.__required_keys__ == frozenset(
        {
            "security",
            "session_date",
            "price_basis",
            "whole_day_variance_5m",
            "whole_day_variance_10m",
            "whole_day_variance_15m",
            "log_ratio_5m_10m",
            "log_ratio_5m_15m",
            "abs_log_gap_5m_10m",
            "abs_log_gap_5m_15m",
            "audit_version",
        }
    )
    row_hints = get_type_hints(MeasurementAuditRow)
    assert row_hints["security"] is SecurityIdentity
    assert row_hints["session_date"] is date
    assert get_args(row_hints["price_basis"]) == ("as_printed", "split_adjusted")
    for field in (
        "whole_day_variance_5m",
        "whole_day_variance_10m",
        "whole_day_variance_15m",
        "log_ratio_5m_10m",
        "log_ratio_5m_15m",
        "abs_log_gap_5m_10m",
        "abs_log_gap_5m_15m",
    ):
        assert row_hints[field] is float
    assert get_args(row_hints["audit_version"]) == ("rv_measurement_audit_v1",)

    assert MeasurementAuditSummary.__required_keys__ == frozenset(
        {
            "security",
            "price_basis",
            "observation_count",
            "pearson_log_rv_5m_10m",
            "pearson_log_rv_5m_15m",
            "spearman_rv_5m_10m",
            "spearman_rv_5m_15m",
            "geometric_bias_5m_vs_10m_pct",
            "geometric_bias_5m_vs_15m_pct",
            "mean_abs_log_gap_5m_10m",
            "mean_abs_log_gap_5m_15m",
            "first_session_date",
            "last_session_date",
            "audit_version",
        }
    )
    summary_hints = get_type_hints(MeasurementAuditSummary)
    assert summary_hints["security"] is SecurityIdentity
    assert get_args(summary_hints["price_basis"]) == ("as_printed", "split_adjusted")
    assert summary_hints["observation_count"] is int
    for field in (
        "pearson_log_rv_5m_10m",
        "pearson_log_rv_5m_15m",
        "spearman_rv_5m_10m",
        "spearman_rv_5m_15m",
        "geometric_bias_5m_vs_10m_pct",
        "geometric_bias_5m_vs_15m_pct",
        "mean_abs_log_gap_5m_10m",
        "mean_abs_log_gap_5m_15m",
    ):
        assert summary_hints[field] is float
    assert summary_hints["first_session_date"] is date
    assert summary_hints["last_session_date"] is date
    assert get_args(summary_hints["audit_version"]) == ("rv_measurement_audit_v1",)
