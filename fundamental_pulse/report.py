from __future__ import annotations

from typing import Any

from fundamental_pulse.models import (
    DataValidationReport,
    ForwardOperatingOutlook,
    GrowthClassification,
    HighFrequencyCorrelationReport,
    OilGasBoundaryAnalysis,
    ProfitAttribution,
    QuarterMetrics,
    QuarterRecord,
    ThesisVerificationReport,
)


def generate_markdown_report(
    current: QuarterRecord,
    metrics: QuarterMetrics,
    classification: GrowthClassification,
    attribution: ProfitAttribution | None = None,
    validation: DataValidationReport | None = None,
    business_judgment: OilGasBoundaryAnalysis | None = None,
    high_frequency: HighFrequencyCorrelationReport | None = None,
    forward_outlook: ForwardOperatingOutlook | None = None,
    *,
    source_label: str | None = None,
    start_period: str | None = None,
    end_period: str | None = None,
    high_freq_summary: dict[str, Any] | None = None,
    thesis_report: ThesisVerificationReport | None = None,
) -> str:
    risks = _risk_lines(metrics)
    attribution_lines = _attribution_lines(attribution, unit=current.unit)
    validation_lines = _validation_lines(validation)
    business_lines = _business_judgment_lines(business_judgment, high_frequency)
    high_frequency_lines = _high_frequency_lines(high_frequency)
    high_freq_summary_lines = _high_freq_summary_lines(high_freq_summary)
    thesis_lines = _thesis_lines(thesis_report)
    financial_snapshot_lines = _financial_snapshot_lines(current)
    source_lines = _source_lines(current, source_label, start_period, end_period)

    if forward_outlook is not None:
        return _generate_forward_report(
            current=current,
            metrics=metrics,
            classification=classification,
            attribution_lines=attribution_lines,
            validation_lines=validation_lines,
            high_frequency_lines=high_frequency_lines,
            forward_outlook=forward_outlook,
            thesis_lines=thesis_lines,
            risks=risks,
            source_lines=source_lines,
        )

    lines = [
        f"# {current.ticker} {current.period} 季度基本面跟踪",
        "",
        "## 一句话结论",
        "",
        f"{current.period} 增长性质判断为：{classification.growth_type}。",
        "",
        "## 核心指标",
        "",
        f"- 收入同比：{_format_pct(metrics.revenue_yoy)}",
        f"- 收入环比：{_format_pct(metrics.revenue_qoq)}",
        f"- 扣非净利润同比：{_format_pct(metrics.deducted_np_yoy)}",
        f"- 扣非净利润环比：{_format_pct(metrics.deducted_np_qoq)}",
        f"- 毛利率：{_format_pct(metrics.gross_margin)}",
        f"- 毛利率同比变化：{_format_pct(metrics.gross_margin_delta_yoy)}",
        f"- 费用率：{_format_pct(metrics.expense_ratio)}",
        f"- 费用率同比变化：{_format_pct(metrics.expense_ratio_delta_yoy)}",
        f"- 经营现金流/归母净利润：{_format_number(metrics.ocf_to_np)}",
        f"- 非经常性损益占比：{_format_pct(metrics.non_recurring_ratio)}",
        "",
        "## 财务数据",
        "",
        *financial_snapshot_lines,
        "",
        "## 增长性质判断",
        "",
        classification.explanation,
        "",
        "## 数据验证",
        "",
        *validation_lines,
        "",
    ]
    if business_judgment is not None:
        lines.extend(["## 业务判断", "", *business_lines, ""])
    if high_freq_summary is not None:
        lines.extend(["## 高频经营信号验证", "", *high_freq_summary_lines, ""])
    if thesis_report is not None:
        lines.extend(["## 投资假设验证", "", *thesis_lines, ""])
    if high_frequency is not None:
        lines.extend(["## 高频因子相关性", "", *high_frequency_lines, ""])
    lines.extend(
        [
            "## 利润归因",
            "",
            *attribution_lines,
            "",
            "## 风险信号",
            "",
            *risks,
            "",
            "## 下一季度跟踪项",
            "",
            "- 收入增速是否延续，并观察扣非净利润是否同步改善。",
            "- 毛利率和费用率变化是否具备持续性。",
            "- 经营现金流、应收账款和存货是否与收入增长匹配。",
            "",
            "## 数据来源与口径",
            "",
            *source_lines,
            "",
            "本报告仅用于研究记录，不构成投资建议。",
            "",
        ]
    )
    return "\n".join(lines)


def _generate_forward_report(
    current: QuarterRecord,
    metrics: QuarterMetrics,
    classification: GrowthClassification,
    attribution_lines: list[str],
    validation_lines: list[str],
    high_frequency_lines: list[str],
    forward_outlook: ForwardOperatingOutlook,
    thesis_lines: list[str],
    risks: list[str],
    source_lines: list[str],
) -> str:
    thesis_section = ["## 投资假设验证", "", *thesis_lines, ""] if thesis_lines else []
    return "\n".join(
        [
            f"# {current.ticker} {forward_outlook.forecast_period} 未来季度经营判断",
            "",
            "## 最终结论",
            "",
            f"- 判断：{forward_outlook.outlook}",
            f"- 置信度：{forward_outlook.confidence_score:.2f}",
            f"- 预测季度：{forward_outlook.forecast_period}",
            f"- 观察基准：{current.period}",
            f"- 目标指标：{forward_outlook.target_metric}",
            f"- 结论：{forward_outlook.conclusion}",
            "",
            "## 核心信号",
            "",
            *_forward_signal_lines(forward_outlook),
            "",
            "## 数据验证",
            "",
            *validation_lines,
            "",
            "## 财务底稿",
            "",
            f"- 历史季度增长性质：{classification.growth_type}",
            *_financial_snapshot_lines(current),
            f"- 收入同比：{_format_pct(metrics.revenue_yoy)}",
            f"- 扣非净利润同比：{_format_pct(metrics.deducted_np_yoy)}",
            f"- 毛利率：{_format_pct(metrics.gross_margin)}",
            f"- 费用率：{_format_pct(metrics.expense_ratio)}",
            f"- 非经常性损益占比：{_format_pct(metrics.non_recurring_ratio)}",
            "",
            "## 高频因子相关性",
            "",
            *high_frequency_lines,
            "",
            *thesis_section,
            "## 利润归因",
            "",
            *attribution_lines,
            "",
            "## 风险与反证信号",
            "",
            *risks,
            *_forward_risk_lines(forward_outlook),
            "",
            "## 跟踪动作",
            "",
            "- 持续更新下一季度高频因子，重点观察支撑信号是否延续。",
            "- 若核心支撑因子转弱，重新计算未来季度经营判断。",
            "- 对高相关但业务逻辑弱的因子，需回到真实业务链条复核。",
            "",
            "## 数据来源与口径",
            "",
            *source_lines,
            "",
            "本报告仅用于研究记录，不构成投资建议。",
            "",
        ]
    )


def _format_pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value * 100:.2f}%"


def _format_number(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.2f}"


def _format_amount(value: float | None, unit: str | None = "CNY") -> str:
    if value is None:
        return "NA"
    return f"{_amount_to_ten_thousand_yuan(value, unit):,.2f} 万元"


def _amount_to_ten_thousand_yuan(value: float, unit: str | None) -> float:
    normalized_unit = (unit or "CNY").strip()
    if normalized_unit in {"万元", "万"}:
        return value
    if normalized_unit in {"亿元", "亿"}:
        return value * 10_000
    return value / 10_000


def _financial_snapshot_lines(current: QuarterRecord) -> list[str]:
    items = [
        ("营业收入", current.revenue),
        ("营业成本", current.operating_cost),
        ("归母净利润", current.net_profit_parent),
        ("扣非归母净利润", current.net_profit_deducted),
        ("非经常性损益", current.non_recurring_gain_loss),
        ("经营活动现金流", current.operating_cash_flow),
        ("应收账款", current.accounts_receivable),
        ("存货", current.inventory),
        ("合同负债", current.contract_liability),
    ]
    lines = [
        f"- {label}：{_format_amount(value, current.unit)}"
        for label, value in items
        if value is not None
    ]
    return lines or ["- 暂无可展示财务金额。"]


def _high_freq_summary_lines(high_freq_summary: dict[str, Any] | None) -> list[str]:
    if high_freq_summary is None:
        return []

    lines = [
        "| 维度 | 判断 |",
        "|---|---|",
        f"| 收入端 | {high_freq_summary.get('revenue_side', 'unknown')} |",
        f"| 成本端 | {high_freq_summary.get('cost_side', 'unknown')} |",
        f"| 利润率 | {high_freq_summary.get('margin_side', 'unknown')} |",
        f"| 现金流 | {high_freq_summary.get('cashflow_side', 'unknown')} |",
        f"| 风险端 | {high_freq_summary.get('risk_side', 'unknown')} |",
        "",
        "### 关键高频证据",
    ]
    key_signals = high_freq_summary.get("key_signals") or []
    if key_signals:
        lines.extend(
            _format_high_freq_signal_line(signal)
            for signal in key_signals
            if isinstance(signal, dict)
        )
    else:
        lines.append("- 暂无可用高频证据。")
    operating_time_sections = high_freq_summary.get("operating_time_sections") or []
    if operating_time_sections:
        lines.extend(
            [
                "",
                "### 经营类数据时间截面",
                "| 日期 | 指标 | 类别 | 数值 | 方向 |",
                "|---|---|---|---:|---|",
            ]
        )
        lines.extend(
            _format_operating_time_section_line(row)
            for row in operating_time_sections
            if isinstance(row, dict)
        )
    lines.extend(
        [
            "",
            "### 对季度增长判断的影响",
            str(high_freq_summary.get("summary") or "高频数据不足，暂不能验证季度增长逻辑。"),
        ]
    )
    return lines


def _thesis_lines(thesis_report: ThesisVerificationReport | None) -> list[str]:
    if thesis_report is None:
        return []

    lines = [
        f"- 假设名称：{thesis_report.thesis_name}",
        f"- 汇总状态：{thesis_report.summary_status}",
        f"- 汇总说明：{thesis_report.summary}",
    ]
    if not thesis_report.drivers:
        lines.append("- 未配置可验证 driver。")
        return lines

    lines.extend(
        [
            "",
            "| Driver | 状态 | 实际 | 判断标准 | 证据 |",
            "|---|---|---:|---|---|",
        ]
    )
    lines.extend(
        f"| {driver.name} | {driver.status} | {_format_thesis_actual(driver.actual)} | "
        f"{driver.expected} | {driver.evidence} |"
        for driver in thesis_report.drivers
    )
    return lines


def _format_thesis_actual(value: float | str | None) -> str:
    if value is None:
        return "NA"
    if isinstance(value, int | float):
        return f"{value:.2f}"
    return value


def _format_high_freq_signal_line(signal: dict[str, Any]) -> str:
    direction = signal.get("direction", "unknown")
    signal_type = signal.get("signal_type", "unknown")
    signal_name = signal.get("signal_name", "unknown")
    evidence = _format_high_freq_signal_evidence(signal)
    return f"- [{direction}][{signal_type}] {signal_name}：{evidence}"


def _format_operating_time_section_line(row: dict[str, Any]) -> str:
    date = row.get("date") or "NA"
    signal_name = row.get("signal_name") or "unknown"
    signal_type = row.get("signal_type") or "unknown"
    direction = row.get("direction") or "unknown"
    value = _format_high_freq_value(
        str(signal_name),
        row.get("value"),
        row.get("unit"),
    )
    return f"| {date} | {signal_name} | {signal_type} | {value or 'NA'} | {direction} |"


def _format_high_freq_signal_evidence(signal: dict[str, Any]) -> str:
    signal_name = str(signal.get("signal_name") or "")
    value = signal.get("value")
    unit = signal.get("unit")
    if value not in (None, ""):
        formatted_value = _format_high_freq_value(signal_name, value, unit)
        if formatted_value is not None:
            return formatted_value
    return str(signal.get("evidence") or "暂无证据摘要。")


def _format_high_freq_value(signal_name: str, value: Any, unit: Any) -> str | None:
    numeric = _parse_numeric(value)
    unit_text = str(unit).strip() if unit not in (None, "") else None
    if numeric is None:
        return f"{value} {unit_text}".strip() if unit_text else str(value)
    if _looks_like_amount_signal(signal_name, unit_text):
        return _format_amount(_to_cny(numeric, unit_text), "CNY")
    return f"{numeric:,.2f} {unit_text}".strip() if unit_text else f"{numeric:,.2f}"


def _looks_like_amount_signal(signal_name: str, unit: str | None) -> bool:
    normalized_name = signal_name.lower()
    if unit in {"元", "万元", "亿元", "cny", "CNY", "rmb", "RMB"}:
        return True
    if any(token in normalized_name for token in ("率", "roe", "roa", "/", "／", "占比")):
        return False
    amount_keywords = (
        "收入",
        "成本",
        "利润",
        "现金流",
        "现金净流量",
        "费用",
        "应收",
        "存货",
        "负债",
        "资产",
    )
    return any(keyword in normalized_name for keyword in amount_keywords)


def _to_cny(value: float, unit: str | None) -> float:
    if unit in {"万元"}:
        return value * 10_000
    if unit in {"亿元"}:
        return value * 100_000_000
    return value


def _parse_numeric(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _source_lines(
    current: QuarterRecord,
    source_label: str | None,
    start_period: str | None,
    end_period: str | None,
) -> list[str]:
    label = source_label or current.source
    if label == "iFinD MCP":
        period_range = (
            f"{start_period or current.period} 至 {end_period or current.period}"
            if start_period or end_period
            else current.period
        )
        return [
            "- 数据源：iFinD MCP",
            f"- 股票代码：{current.ticker}",
            f"- 报告期：{period_range}",
            "- 内部数值单位：CNY 元",
            "- 报告金额单位：万元",
            "- 口径说明：如 iFinD 返回累计口径，则已转换为单季度口径；资产负债表项目未做差分。",
            "- 非经常性损益贡献为单独观察项，不代表扣非利润变化的完整拆解。",
        ]
    return [
        f"- 数据来源：{current.source}",
        "- 报告金额单位：万元",
        "- 财务计算使用确定性规则；累计口径已转为单季度口径。",
        "- 非经常性损益贡献为单独观察项，不代表扣非利润变化的完整拆解。",
    ]


def _attribution_lines(
    attribution: ProfitAttribution | None,
    unit: str | None = "CNY",
) -> list[str]:
    if attribution is None:
        return ["- 暂无可比同期数据，未生成利润归因。"]

    positive = ", ".join(attribution.top_positive) if attribution.top_positive else "NA"
    negative = ", ".join(attribution.top_negative) if attribution.top_negative else "NA"

    return [
        f"- 扣非净利润变化：{_format_amount(attribution.profit_delta, unit)}",
        f"- 收入贡献：{_format_amount(attribution.revenue_contribution, unit)}",
        f"- 毛利率贡献：{_format_amount(attribution.gross_margin_contribution, unit)}",
        f"- 费用贡献：{_format_amount(attribution.expense_contribution, unit)}",
        f"- 非经常性损益贡献：{_format_amount(attribution.non_recurring_contribution, unit)}",
        f"- 主要正向项：{positive}",
        f"- 主要负向项：{negative}",
    ]


def _validation_lines(validation: DataValidationReport | None) -> list[str]:
    if validation is None:
        return ["- 未传入数据验证结果。"]

    lines = [
        f"- 状态：{validation.status}",
        f"- 可信度评分：{validation.confidence_score:.2f}",
    ]
    if not validation.issues:
        lines.append("- 未发现明确数据异常。")
        return lines

    lines.extend(
        f"- {issue.severity} / {issue.code} / {issue.period or 'NA'}：{issue.message}"
        for issue in validation.issues[:5]
    )
    return lines


def _business_judgment_lines(
    business_judgment: OilGasBoundaryAnalysis | None,
    high_frequency: HighFrequencyCorrelationReport | None,
) -> list[str]:
    if business_judgment is None:
        if high_frequency is not None:
            return ["- 已按公司相关高频因子进行业务判断，详见“高频因子相关性”。"]
        return ["- 未传入行业变量，当前仅输出财务规则判断。"]

    lines = [
        f"- 油价边界：{business_judgment.oil_price_floor:.2f}"
        f"-{business_judgment.oil_price_ceiling:.2f}",
        f"- 基准油价：{business_judgment.base_oil_price:.2f}",
        f"- TTM 扣非利润基准：{business_judgment.base_profit_ttm:.2f}",
        f"- 油价每变动 1 美元的利润敏感度："
        f"{business_judgment.profit_sensitivity_per_usd:.2f}",
        f"- 估值倍数边界：{business_judgment.valuation_multiple_low:.2f}"
        f"-{business_judgment.valuation_multiple_high:.2f}",
        f"- 结论：{business_judgment.conclusion}",
        "",
        "| 情景 | 油价 | 利润中枢 | 估值下沿 | 估值上沿 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {scenario.name} | {scenario.oil_price:.2f} | "
        f"{scenario.profit_center:.2f} | {scenario.valuation_low:.2f} | "
        f"{scenario.valuation_high:.2f} |"
        for scenario in business_judgment.scenarios
    )
    return lines


def _high_frequency_lines(high_frequency: HighFrequencyCorrelationReport | None) -> list[str]:
    if high_frequency is None:
        return ["- 未传入高频因子数据，当前未做相关性分析。"]

    lines = [
        f"- 目标指标：{high_frequency.target_metric}",
        f"- 样本季度数：{high_frequency.sample_size}",
        f"- 结论：{high_frequency.conclusion}",
    ]
    if not high_frequency.correlations:
        return lines

    lines.extend(
        [
            "",
            "| 因子 | 滞后季度 | 相关系数 | 样本数 | 判断 |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    lines.extend(
        f"| {item.factor_label} | {item.lag_quarters} | {item.correlation:.2f} | "
        f"{item.observations} | {item.interpretation} |"
        for item in high_frequency.correlations[:5]
    )
    return lines


def _forward_outlook_lines(forward_outlook: ForwardOperatingOutlook | None) -> list[str]:
    if forward_outlook is None:
        return ["- 未传入下一季度高频数据，当前未形成未来季度经营判断。"]

    lines = [
        f"- 预测季度：{forward_outlook.forecast_period}",
        f"- 目标指标：{forward_outlook.target_metric}",
        f"- 方向判断：{forward_outlook.outlook}",
        f"- 置信度评分：{forward_outlook.confidence_score:.2f}",
        f"- 结论：{forward_outlook.conclusion}",
    ]
    if forward_outlook.signals:
        lines.extend(
            [
                "",
                "| 因子 | 当前值 | 下一季度值 | 变化率 | 相关系数 | 影响 |",
                "| --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        lines.extend(
            f"| {signal.factor_label} | {signal.current_value:.2f} | "
            f"{signal.forecast_value:.2f} | {_format_pct(signal.change_rate)} | "
            f"{signal.correlation:.2f} | {signal.rationale} |"
            for signal in forward_outlook.signals[:5]
        )
    if forward_outlook.risks:
        lines.append("")
        lines.extend(f"- 风险：{risk}" for risk in forward_outlook.risks[:3])
    return lines


def _forward_signal_lines(forward_outlook: ForwardOperatingOutlook) -> list[str]:
    if not forward_outlook.signals:
        return ["- 暂无可用高频信号。"]

    lines = [
        "| 因子 | 当前值 | 下一季度值 | 变化率 | 相关系数 | 影响 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| {signal.factor_label} | {signal.current_value:.2f} | "
        f"{signal.forecast_value:.2f} | {_format_pct(signal.change_rate)} | "
        f"{signal.correlation:.2f} | {signal.rationale} |"
        for signal in forward_outlook.signals[:5]
    )
    return lines


def _forward_risk_lines(forward_outlook: ForwardOperatingOutlook) -> list[str]:
    if not forward_outlook.risks:
        return []
    return [f"- 前瞻风险：{risk}" for risk in forward_outlook.risks[:3]]


def _risk_lines(metrics: QuarterMetrics) -> list[str]:
    risks: list[str] = []
    if metrics.ocf_to_np is not None and metrics.ocf_to_np < 0.50:
        risks.append("- 经营现金流/归母净利润低于 0.50，利润与现金流存在背离。")
    if metrics.non_recurring_ratio is not None and metrics.non_recurring_ratio > 0.30:
        risks.append("- 非经常性损益占比较高，需要区分经常性经营改善和一次性收益。")
    if metrics.ar_growth_gap_vs_revenue is not None and metrics.ar_growth_gap_vs_revenue > 0.10:
        risks.append("- 应收账款增速明显高于收入增速，需跟踪回款质量。")
    if (
        metrics.inventory_growth_gap_vs_revenue is not None
        and metrics.inventory_growth_gap_vs_revenue > 0.10
    ):
        risks.append("- 存货增速明显高于收入增速，需跟踪库存消化。")
    return risks or ["- 未触发明确风险信号。"]
