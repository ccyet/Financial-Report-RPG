import pytest

from fundamental_pulse.analysis import calculate_metrics
from fundamental_pulse.models import QuarterRecord


def test_calculate_metrics_yoy_margin_expense_cashflow():
    records = [
        QuarterRecord(
            ticker="300750.SZ",
            period="2024Q1",
            revenue=100,
            operating_cost=60,
            selling_expense=5,
            admin_expense=3,
            rd_expense=4,
            financial_expense=1,
            net_profit_parent=12,
            net_profit_deducted=10,
            non_recurring_gain_loss=2,
            operating_cash_flow=18,
            accounts_receivable=40,
            inventory=25,
        ),
        QuarterRecord(
            ticker="300750.SZ",
            period="2025Q1",
            revenue=130,
            operating_cost=75,
            selling_expense=6,
            admin_expense=4,
            rd_expense=5,
            financial_expense=1,
            net_profit_parent=18,
            net_profit_deducted=16,
            non_recurring_gain_loss=1,
            operating_cash_flow=27,
            accounts_receivable=54,
            inventory=30,
        ),
    ]

    metrics = calculate_metrics(records)
    current = metrics[-1]

    assert current.revenue_yoy == pytest.approx(0.30)
    assert current.gross_margin == pytest.approx((130 - 75) / 130)
    assert current.gross_margin_delta_yoy == pytest.approx(((130 - 75) / 130) - 0.40)
    assert current.deducted_np_yoy == pytest.approx(0.60)
    assert current.expense_ratio == pytest.approx((6 + 4 + 5 + 1) / 130)
    assert current.expense_ratio_delta_yoy == pytest.approx(((6 + 4 + 5 + 1) / 130) - 0.13)
    assert current.ocf_to_np == pytest.approx(1.5)
    assert current.non_recurring_ratio == pytest.approx(1 / 18)
    assert current.ar_growth_gap_vs_revenue == pytest.approx((54 / 40 - 1) - 0.30)
    assert current.inventory_growth_gap_vs_revenue == pytest.approx((30 / 25 - 1) - 0.30)


def test_calculate_metrics_returns_none_when_denominator_is_missing_or_zero():
    records = [
        QuarterRecord(ticker="300750.SZ", period="2024Q1", revenue=0, net_profit_parent=0),
        QuarterRecord(ticker="300750.SZ", period="2025Q1", revenue=130, net_profit_parent=0),
    ]

    current = calculate_metrics(records)[-1]

    assert current.revenue_yoy is None
    assert current.gross_margin is None
    assert current.ocf_to_np is None
