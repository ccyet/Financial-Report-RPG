import pytest

from fundamental_pulse.business import analyze_oil_gas_boundary, validate_financial_records
from fundamental_pulse.models import QuarterRecord


def test_validate_financial_records_flags_missing_core_and_reconciliation_gap():
    records = [
        QuarterRecord(
            ticker="600000.SH",
            period="2025Q1",
            revenue=None,
            net_profit_parent=10,
            net_profit_deducted=8,
            non_recurring_gain_loss=10,
            operating_cash_flow=9,
        )
    ]

    validation = validate_financial_records(records)

    assert validation.status == "fail"
    assert validation.confidence_score < 1
    assert any(issue.code == "missing_core_field" for issue in validation.issues)
    assert any(issue.code == "non_recurring_reconciliation_gap" for issue in validation.issues)


def test_analyze_oil_gas_boundary_maps_oil_price_to_profit_and_valuation_ranges():
    records = [
        QuarterRecord(ticker="600000.SH", period="2025Q1", net_profit_deducted=10),
        QuarterRecord(ticker="600000.SH", period="2025Q2", net_profit_deducted=12),
        QuarterRecord(ticker="600000.SH", period="2025Q3", net_profit_deducted=13),
        QuarterRecord(ticker="600000.SH", period="2025Q4", net_profit_deducted=15),
    ]

    boundary = analyze_oil_gas_boundary(
        records=records,
        current_period="2025Q4",
        base_oil_price=80,
        oil_price_floor=60,
        oil_price_ceiling=100,
        profit_sensitivity_per_usd=2,
        valuation_multiple_low=8,
        valuation_multiple_high=12,
    )

    assert boundary.base_profit_ttm == pytest.approx(50)
    assert boundary.scenarios[0].oil_price == 60
    assert boundary.scenarios[0].profit_center == pytest.approx(10)
    assert boundary.scenarios[0].valuation_low == pytest.approx(80)
    assert boundary.scenarios[0].valuation_high == pytest.approx(120)
    assert boundary.scenarios[-1].oil_price == 100
    assert boundary.scenarios[-1].profit_center == pytest.approx(90)
    assert "利润中枢" in boundary.conclusion
    assert "估值边界" in boundary.conclusion
