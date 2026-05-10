from fundamental_pulse.models import (
    DataValidationReport,
    ForwardFactorSignal,
    ForwardOperatingOutlook,
    GrowthClassification,
    HighFrequencyCorrelation,
    HighFrequencyCorrelationReport,
    OilGasBoundaryAnalysis,
    OilGasScenario,
    ProfitAttribution,
    QuarterMetrics,
    QuarterRecord,
    ThesisDriverVerification,
    ThesisVerificationReport,
    ValidationIssue,
)
from fundamental_pulse.report import generate_markdown_report


def test_report_contains_required_sections_and_disclaimer():
    report = generate_markdown_report(
        current=QuarterRecord(
            ticker="300750.SZ",
            period="2025Q4",
            revenue=130,
            net_profit_parent=18,
            net_profit_deducted=16,
            source="mock_ifind_mcp",
        ),
        metrics=QuarterMetrics(
            ticker="300750.SZ",
            period="2025Q4",
            revenue_yoy=0.30,
            deducted_np_yoy=0.60,
            gross_margin=0.42,
            gross_margin_delta_yoy=0.02,
            expense_ratio=0.12,
            ocf_to_np=1.50,
        ),
        classification=GrowthClassification(
            growth_type="收入驱动型增长",
            explanation="触发收入驱动型增长规则。",
            triggered_rules=["收入驱动型增长"],
        ),
        attribution=ProfitAttribution(
            ticker="300750.SZ",
            period="2025Q4",
            profit_delta=6,
            revenue_contribution=12,
            gross_margin_contribution=3,
            expense_contribution=-1,
            non_recurring_contribution=0,
            top_positive=["收入贡献", "毛利率贡献"],
            top_negative=["费用贡献"],
        ),
    )

    assert "一句话结论" in report
    assert "核心指标" in report
    assert "增长性质判断" in report
    assert "利润归因" in report
    assert "数据来源与口径" in report
    assert "不构成投资建议" in report
    assert "买入" not in report
    assert "目标价" not in report


def test_standard_report_omits_high_frequency_placeholders_when_not_requested():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
    )

    assert "高频因子相关性" not in report
    assert "未来季度经营判断" not in report


def test_report_formats_amounts_in_ten_thousand_yuan_with_commas():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4", source="iFinD MCP"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        attribution=ProfitAttribution(
            ticker="300750.SZ",
            period="2025Q4",
            profit_delta=8_072_130_000,
            revenue_contribution=5_662_685_141.79,
            gross_margin_contribution=18_529_264_858.21,
            expense_contribution=-11_069_922_600,
            non_recurring_contribution=351_430_000,
        ),
        source_label="iFinD MCP",
        start_period="2022Q1",
        end_period="2024Q4",
    )

    assert "- 扣非净利润变化：807,213.00 万元" in report
    assert "- 收入贡献：566,268.51 万元" in report
    assert "- 费用贡献：-1,106,992.26 万元" in report
    assert "- 报告金额单位：万元" in report


def test_report_formats_current_financial_data_in_ten_thousand_yuan_with_commas():
    report = generate_markdown_report(
        current=QuarterRecord(
            ticker="300750.SZ",
            period="2024Q4",
            revenue=140_629_850_000,
            operating_cost=100_956_150_000,
            net_profit_parent=23_167_170_000,
            net_profit_deducted=20_888_640_000,
            non_recurring_gain_loss=2_278_530_000,
            operating_cash_flow=46_334_340_000,
            accounts_receivable=76_403_260_000,
            inventory=94_526_240_000,
        ),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2024Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
    )

    assert "## 财务数据" in report
    assert "- 营业收入：14,062,985.00 万元" in report
    assert "- 营业成本：10,095,615.00 万元" in report
    assert "- 归母净利润：2,316,717.00 万元" in report
    assert "- 经营活动现金流：4,633,434.00 万元" in report
    assert "140629850000" not in report


def test_report_respects_mock_financial_unit_when_already_ten_thousand_yuan():
    report = generate_markdown_report(
        current=QuarterRecord(
            ticker="300750.SZ",
            period="2025Q4",
            unit="万元",
            revenue=155,
            operating_cost=100,
            net_profit_parent=18,
            net_profit_deducted=12.5,
            non_recurring_gain_loss=6,
            operating_cash_flow=18,
        ),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        attribution=ProfitAttribution(
            ticker="300750.SZ",
            period="2025Q4",
            profit_delta=1.5,
            revenue_contribution=15,
            expense_contribution=-2,
        ),
    )

    assert "- 营业收入：155.00 万元" in report
    assert "- 归母净利润：18.00 万元" in report
    assert "- 扣非净利润变化：1.50 万元" in report
    assert "- 收入贡献：15.00 万元" in report


def test_report_contains_validation_and_business_judgment_sections():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="600000.SH", period="2025Q4", source="mock_ifind_mcp"),
        metrics=QuarterMetrics(ticker="600000.SH", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        validation=DataValidationReport(
            status="warning",
            confidence_score=0.8,
            issues=[
                ValidationIssue(
                    severity="warning",
                    code="non_recurring_reconciliation_gap",
                    period="2025Q4",
                    field="non_recurring_gain_loss",
                    message="非经常性损益与归母/扣非差额不一致。",
                )
            ],
        ),
        business_judgment=OilGasBoundaryAnalysis(
            ticker="600000.SH",
            period="2025Q4",
            base_oil_price=80,
            oil_price_floor=60,
            oil_price_ceiling=100,
            profit_sensitivity_per_usd=2,
            valuation_multiple_low=8,
            valuation_multiple_high=12,
            base_profit_ttm=50,
            scenarios=[
                OilGasScenario(
                    name="压力情景",
                    oil_price=60,
                    profit_center=10,
                    valuation_low=80,
                    valuation_high=120,
                )
            ],
            conclusion="油价边界 60-100，对应利润中枢 10-90，估值边界 80-1080。",
        ),
    )

    assert "数据验证" in report
    assert "业务判断" in report
    assert "油价边界" in report
    assert "利润中枢" in report
    assert "估值边界" in report


def test_report_contains_high_frequency_correlation_section():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4", source="mock_ifind_mcp"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        high_frequency=HighFrequencyCorrelationReport(
            ticker="300750.SZ",
            target_metric="revenue_yoy",
            sample_size=4,
            correlations=[
                HighFrequencyCorrelation(
                    factor_name="power_battery_installation",
                    factor_label="动力电池装机量",
                    target_metric="revenue_yoy",
                    lag_quarters=0,
                    correlation=0.92,
                    observations=4,
                    direction="positive",
                    interpretation="动力电池装机量与收入同比正相关。",
                )
            ],
            conclusion="动力电池装机量与收入同比相关性最高。",
        ),
    )

    assert "高频因子相关性" in report
    assert "动力电池装机量" in report
    assert "相关系数" in report


def test_report_contains_thesis_verification_section_without_advice_words():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        thesis_report=ThesisVerificationReport(
            ticker="300750.SZ",
            period="2025Q4",
            thesis_name="宁德时代季度经营假设",
            summary_status="pass",
            summary="4 个 driver 通过，0 个失败，0 个未知。",
            drivers=[
                ThesisDriverVerification(
                    id="revenue_growth",
                    name="收入增速",
                    status="pass",
                    actual=0.3,
                    expected="revenue_yoy >= 0.1",
                    evidence="revenue_yoy=30.00%，满足 >= 10.00%。",
                )
            ],
        ),
    )

    assert "## 投资假设验证" in report
    assert "汇总状态：pass" in report
    assert "收入增速" in report
    assert "不构成投资建议" in report
    assert "买入" not in report
    assert "卖出" not in report
    assert "目标价" not in report


def test_report_contains_forward_operating_outlook_section():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4", source="mock_ifind_mcp"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        forward_outlook=ForwardOperatingOutlook(
            ticker="300750.SZ",
            current_period="2025Q4",
            forecast_period="2026Q1",
            target_metric="revenue_yoy",
            outlook="改善",
            confidence_score=0.73,
            signals=[
                ForwardFactorSignal(
                    factor_name="power_battery_installation",
                    factor_label="动力电池装机量",
                    current_period="2025Q4",
                    forecast_period="2026Q1",
                    current_value=100,
                    forecast_value=115,
                    change_rate=0.15,
                    correlation=0.90,
                    expected_effect="support",
                    rationale="高频因子上行且与目标指标正相关。",
                )
            ],
            risks=[],
            conclusion="下一季度经营情况倾向改善。",
        ),
    )

    assert "未来季度经营判断" in report
    assert "2026Q1" in report
    assert "改善" in report
    assert "动力电池装机量" in report


def test_forward_report_uses_decision_first_output_format():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4", source="mock_ifind_mcp"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        validation=DataValidationReport(status="pass", confidence_score=1.0),
        forward_outlook=ForwardOperatingOutlook(
            ticker="300750.SZ",
            current_period="2025Q4",
            forecast_period="2026Q1",
            target_metric="revenue_yoy",
            outlook="改善",
            confidence_score=0.73,
            signals=[
                ForwardFactorSignal(
                    factor_name="power_battery_installation",
                    factor_label="动力电池装机量",
                    current_period="2025Q4",
                    forecast_period="2026Q1",
                    current_value=100,
                    forecast_value=115,
                    change_rate=0.15,
                    correlation=0.90,
                    expected_effect="support",
                    rationale="高频因子上行且与目标指标正相关。",
                )
            ],
            risks=[],
            conclusion="下一季度经营情况倾向改善。",
        ),
    )

    assert report.startswith("# 300750.SZ 2026Q1 未来季度经营判断")
    assert "## 最终结论" in report
    assert "- 判断：改善" in report
    assert "- 置信度：0.73" in report
    assert report.index("## 最终结论") < report.index("## 核心信号")
    assert report.index("## 核心信号") < report.index("## 数据验证")
    assert report.index("## 数据验证") < report.index("## 财务底稿")
    assert "买入" not in report
    assert "目标价" not in report
