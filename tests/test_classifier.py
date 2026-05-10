from fundamental_pulse.analysis import classify_growth
from fundamental_pulse.models import QuarterMetrics


def _metrics(**overrides):
    values = {
        "ticker": "300750.SZ",
        "period": "2025Q4",
        "revenue_yoy": 0.08,
        "deducted_np_yoy": 0.08,
        "gross_margin_delta_yoy": 0.00,
        "expense_ratio_delta_yoy": 0.00,
        "ocf_to_np": 0.90,
        "non_recurring_ratio": 0.05,
        "ar_growth_gap_vs_revenue": 0.00,
        "inventory_growth_gap_vs_revenue": 0.00,
    }
    values.update(overrides)
    return QuarterMetrics(**values)


def test_classifier_non_recurring_driven():
    result = classify_growth(_metrics(non_recurring_ratio=0.35))

    assert result.growth_type == "非经常性驱动"
    assert result.triggered_rules


def test_classifier_cashflow_divergence():
    result = classify_growth(_metrics(deducted_np_yoy=0.20, ocf_to_np=0.40))

    assert result.growth_type == "利润增长但现金流背离"
    assert result.triggered_rules


def test_classifier_revenue_driven_growth():
    result = classify_growth(
        _metrics(
            revenue_yoy=0.22,
            deducted_np_yoy=0.18,
            gross_margin_delta_yoy=-0.01,
            ocf_to_np=0.90,
            non_recurring_ratio=0.05,
        )
    )

    assert result.growth_type == "收入驱动型增长"
    assert result.triggered_rules


def test_classifier_gross_margin_driven_growth():
    result = classify_growth(
        _metrics(revenue_yoy=0.08, deducted_np_yoy=0.25, gross_margin_delta_yoy=0.04)
    )

    assert result.growth_type == "毛利率改善型利润增长"
    assert result.triggered_rules


def test_classifier_expense_compression_growth():
    result = classify_growth(
        _metrics(
            revenue_yoy=0.05,
            deducted_np_yoy=0.18,
            gross_margin_delta_yoy=0.00,
            expense_ratio_delta_yoy=-0.04,
        )
    )

    assert result.growth_type == "费用压缩型利润增长"
    assert result.triggered_rules


def test_classifier_revenue_growth_but_profit_deteriorates():
    result = classify_growth(_metrics(revenue_yoy=0.20, deducted_np_yoy=0.02))

    assert result.growth_type == "收入增长但利润恶化"
    assert result.triggered_rules


def test_classifier_working_capital_risk():
    result = classify_growth(_metrics(ar_growth_gap_vs_revenue=0.15))

    assert result.growth_type == "营运资本风险型增长"
    assert result.triggered_rules


def test_classifier_data_insufficient():
    result = classify_growth(_metrics(revenue_yoy=None))

    assert result.growth_type == "数据不足"
    assert "revenue_yoy" in result.missing_fields
