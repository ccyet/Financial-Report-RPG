from fundamental_pulse.highfreq import (
    mock_highfreq_signals,
    parse_highfreq_response,
    summarize_high_freq_signals,
)
from fundamental_pulse.models import HighFreqSignal


def test_summarize_high_freq_signals():
    signals = [
        HighFreqSignal(
            ticker="300750.SZ",
            signal_type="revenue",
            signal_name="订单增加",
            direction="positive",
        ),
        HighFreqSignal(
            ticker="300750.SZ",
            signal_type="cost",
            signal_name="原材料价格下降",
            direction="positive",
        ),
        HighFreqSignal(
            ticker="300750.SZ",
            signal_type="cashflow",
            signal_name="存货增加",
            direction="negative",
        ),
        HighFreqSignal(
            ticker="300750.SZ",
            signal_type="risk",
            signal_name="政策不确定",
            direction="negative",
        ),
    ]

    summary = summarize_high_freq_signals(signals)

    assert summary["revenue_side"] == "positive"
    assert summary["cost_side"] == "positive"
    assert summary["cashflow_side"] == "negative"
    assert summary["risk_side"] == "negative"
    assert summary["key_signals"][0]["signal_name"] == "政策不确定"


def test_empty_high_freq_signals_are_unknown():
    summary = summarize_high_freq_signals([])

    assert summary["revenue_side"] == "unknown"
    assert summary["cost_side"] == "unknown"
    assert summary["margin_side"] == "unknown"
    assert summary["cashflow_side"] == "unknown"
    assert summary["risk_side"] == "unknown"
    assert summary["key_signals"] == []


def test_key_signals_prioritize_known_types_when_direction_unknown():
    summary = summarize_high_freq_signals(
        [
            HighFreqSignal(
                ticker="300750.SZ",
                signal_type="unknown",
                signal_name="净利润",
                direction="unknown",
            ),
            HighFreqSignal(
                ticker="300750.SZ",
                signal_type="revenue",
                signal_name="营业总收入",
                direction="unknown",
            ),
            HighFreqSignal(
                ticker="300750.SZ",
                signal_type="cashflow",
                signal_name="经营活动现金净流量",
                direction="unknown",
            ),
        ]
    )

    assert [signal["signal_name"] for signal in summary["key_signals"]] == [
        "经营活动现金净流量",
        "营业总收入",
        "净利润",
    ]


def test_mock_highfreq_signals_cover_more_battery_chain_data():
    signals = mock_highfreq_signals("300750.SZ", lookback_days=90)
    names = {signal.signal_name for signal in signals}
    signal_types = {signal.signal_type for signal in signals}

    assert len(signals) >= 14
    assert {
        "动力电池装机量同比增长",
        "储能系统中标增加",
        "碳酸锂价格低位运行",
        "正极材料排产改善",
        "电解液价格竞争",
        "欧洲关税政策不确定",
    }.issubset(names)
    assert {"revenue", "cost", "margin", "cashflow", "risk", "policy", "industry"}.issubset(
        signal_types
    )


def test_summarize_adds_non_financial_operating_time_sections():
    signals = parse_highfreq_response(
        (
            "|日期|动力电池装机量（单位：GWh）|碳酸锂价格（单位：万元/吨）|营业总收入(TTM)|\n"
            "|---|---|---|---|\n"
            "|2026-03-31|55.2|7.8|423701834000.00|\n"
            "|2026-02-28|49.1|8.2|423701834000.00|\n"
        ),
        ticker="300750.SZ",
    )

    summary = summarize_high_freq_signals(signals)

    assert summary["operating_time_sections"] == [
        {
            "date": "2026-03-31",
            "signal_type": "revenue",
            "signal_name": "动力电池装机量",
            "value": "55.2",
            "unit": "GWh",
            "direction": "unknown",
            "evidence": "动力电池装机量=55.2",
        },
        {
            "date": "2026-03-31",
            "signal_type": "cost",
            "signal_name": "碳酸锂价格",
            "value": "7.8",
            "unit": "万元/吨",
            "direction": "unknown",
            "evidence": "碳酸锂价格=7.8",
        },
        {
            "date": "2026-02-28",
            "signal_type": "revenue",
            "signal_name": "动力电池装机量",
            "value": "49.1",
            "unit": "GWh",
            "direction": "unknown",
            "evidence": "动力电池装机量=49.1",
        },
        {
            "date": "2026-02-28",
            "signal_type": "cost",
            "signal_name": "碳酸锂价格",
            "value": "8.2",
            "unit": "万元/吨",
            "direction": "unknown",
            "evidence": "碳酸锂价格=8.2",
        },
    ]
    assert all("营业总收入" not in row["signal_name"] for row in summary["operating_time_sections"])


def test_operating_time_sections_exclude_segment_financial_fields():
    signals = parse_highfreq_response(
        (
            "|日期|主营构成-项目名称(按产品)__排名:第1名__|主营构成-项目收入(按产品)__排名:第1名__|"
            "主营构成-项目成本(按产品)__排名:第1名__|动力电池装机量（单位：GWh）|\n"
            "|---|---|---|---|---|\n"
            "|2025-12-31|动力电池系统|316506369000.00|241064397000.00|55.2|\n"
        ),
        ticker="300750.SZ",
    )

    summary = summarize_high_freq_signals(signals)

    assert [row["signal_name"] for row in summary["operating_time_sections"]] == [
        "动力电池装机量"
    ]
