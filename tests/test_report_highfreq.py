from fundamental_pulse.models import GrowthClassification, QuarterMetrics, QuarterRecord
from fundamental_pulse.report import generate_markdown_report


def test_report_contains_highfreq_section_when_enabled():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        high_freq_summary={
            "revenue_side": "positive",
            "cost_side": "positive",
            "margin_side": "neutral",
            "cashflow_side": "negative",
            "risk_side": "negative",
            "summary": "高频数据对收入端和成本端有支持，但现金流和风险端存在压力。",
            "key_signals": [
                {
                    "date": "2024-04-10",
                    "signal_type": "revenue",
                    "signal_name": "海外储能订单增加",
                    "direction": "positive",
                    "evidence": "近 90 天海外储能相关订单披露增加。",
                }
            ],
        },
    )

    assert "高频经营信号验证" in report
    assert "| 收入端 | positive |" in report
    assert "关键高频证据" in report
    assert "[positive][revenue] 海外储能订单增加" in report


def test_report_does_not_fabricate_highfreq_section_when_disabled():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        high_freq_summary=None,
    )

    assert "高频经营信号验证" not in report


def test_highfreq_financial_signal_values_use_ten_thousand_yuan_with_commas():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        high_freq_summary={
            "revenue_side": "unknown",
            "cost_side": "unknown",
            "margin_side": "unknown",
            "cashflow_side": "unknown",
            "risk_side": "unknown",
            "summary": "高频数据不足。",
            "key_signals": [
                {
                    "signal_type": "revenue",
                    "signal_name": "营业总收入(TTM)",
                    "direction": "unknown",
                    "value": "423701834000.00",
                    "unit": None,
                    "evidence": "营业总收入(TTM)=423701834000.00",
                },
                {
                    "signal_type": "margin",
                    "signal_name": "净利润／营业总收入(TTM)",
                    "direction": "unknown",
                    "value": "18.12",
                    "unit": None,
                    "evidence": "净利润／营业总收入(TTM)=18.12",
                },
            ],
        },
    )

    assert "营业总收入(TTM)：42,370,183.40 万元" in report
    assert "净利润／营业总收入(TTM)：18.12" in report
    assert "423701834000.00" not in report


def test_report_contains_operating_time_section_for_non_financial_data():
    report = generate_markdown_report(
        current=QuarterRecord(ticker="300750.SZ", period="2025Q4"),
        metrics=QuarterMetrics(ticker="300750.SZ", period="2025Q4"),
        classification=GrowthClassification(
            growth_type="中性或待判断",
            explanation="未触发明确增长性质规则。",
        ),
        high_freq_summary={
            "revenue_side": "unknown",
            "cost_side": "unknown",
            "margin_side": "unknown",
            "cashflow_side": "unknown",
            "risk_side": "unknown",
            "summary": "高频数据不足。",
            "key_signals": [],
            "operating_time_sections": [
                {
                    "date": "2026-03-31",
                    "signal_type": "revenue",
                    "signal_name": "动力电池装机量",
                    "value": "55.2",
                    "unit": "GWh",
                    "direction": "unknown",
                },
                {
                    "date": "2026-03-31",
                    "signal_type": "cost",
                    "signal_name": "碳酸锂价格",
                    "value": "7.8",
                    "unit": "万元/吨",
                    "direction": "unknown",
                },
            ],
        },
    )

    assert "### 经营类数据时间截面" in report
    assert "| 2026-03-31 | 动力电池装机量 | revenue | 55.20 GWh | unknown |" in report
    assert "| 2026-03-31 | 碳酸锂价格 | cost | 7.80 万元/吨 | unknown |" in report
