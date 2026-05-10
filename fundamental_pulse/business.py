from __future__ import annotations

from fundamental_pulse.models import (
    DataValidationReport,
    OilGasBoundaryAnalysis,
    OilGasScenario,
    QuarterMetrics,
    QuarterRecord,
    ValidationIssue,
)

CORE_FIELDS = ("revenue", "net_profit_parent", "net_profit_deducted")


def validate_financial_records(
    records: list[QuarterRecord],
    metrics: list[QuarterMetrics] | None = None,
) -> DataValidationReport:
    issues: list[ValidationIssue] = []
    seen: set[tuple[str, str]] = set()

    for record in records:
        key = (record.ticker, record.period)
        if key in seen:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_period",
                    period=record.period,
                    message=f"{record.ticker} {record.period} 存在重复记录。",
                )
            )
        seen.add(key)

        for field in CORE_FIELDS:
            if getattr(record, field) is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="missing_core_field",
                        period=record.period,
                        field=field,
                        message=f"{record.period} 缺少核心字段 {field}。",
                    )
                )

        if record.operating_cash_flow is None:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="missing_cashflow",
                    period=record.period,
                    field="operating_cash_flow",
                    message=f"{record.period} 缺少经营现金流，现金流背离判断可信度下降。",
                )
            )

        if record.revenue is not None and record.revenue <= 0:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="non_positive_revenue",
                    period=record.period,
                    field="revenue",
                    message=f"{record.period} 收入小于或等于 0，指标计算不可用。",
                )
            )

        _append_non_recurring_check(record, issues)

    for metric in metrics or []:
        _append_metric_checks(metric, issues)

    return _build_validation_report(issues)


def analyze_oil_gas_boundary(
    records: list[QuarterRecord],
    current_period: str,
    base_oil_price: float,
    oil_price_floor: float,
    oil_price_ceiling: float,
    profit_sensitivity_per_usd: float,
    valuation_multiple_low: float,
    valuation_multiple_high: float,
) -> OilGasBoundaryAnalysis:
    if oil_price_floor > oil_price_ceiling:
        raise ValueError("oil_price_floor must be less than or equal to oil_price_ceiling.")
    if valuation_multiple_low > valuation_multiple_high:
        raise ValueError(
            "valuation_multiple_low must be less than or equal to valuation_multiple_high."
        )

    current = next((record for record in records if record.period == current_period), None)
    if current is None:
        raise ValueError(f"Period {current_period} is not available.")

    trailing_records = sorted(
        [record for record in records if record.period <= current_period],
        key=lambda record: record.period,
    )[-4:]
    if len(trailing_records) < 4:
        raise ValueError("At least four quarters are required for oil-gas TTM profit boundary.")

    profits = [record.net_profit_deducted for record in trailing_records]
    if any(profit is None for profit in profits):
        raise ValueError("All trailing four quarters must include net_profit_deducted.")

    base_profit_ttm = sum(profit for profit in profits if profit is not None)
    scenarios = [
        _oil_gas_scenario(
            name="压力情景",
            oil_price=oil_price_floor,
            base_oil_price=base_oil_price,
            base_profit_ttm=base_profit_ttm,
            profit_sensitivity_per_usd=profit_sensitivity_per_usd,
            valuation_multiple_low=valuation_multiple_low,
            valuation_multiple_high=valuation_multiple_high,
        ),
        _oil_gas_scenario(
            name="基准情景",
            oil_price=base_oil_price,
            base_oil_price=base_oil_price,
            base_profit_ttm=base_profit_ttm,
            profit_sensitivity_per_usd=profit_sensitivity_per_usd,
            valuation_multiple_low=valuation_multiple_low,
            valuation_multiple_high=valuation_multiple_high,
        ),
        _oil_gas_scenario(
            name="乐观情景",
            oil_price=oil_price_ceiling,
            base_oil_price=base_oil_price,
            base_profit_ttm=base_profit_ttm,
            profit_sensitivity_per_usd=profit_sensitivity_per_usd,
            valuation_multiple_low=valuation_multiple_low,
            valuation_multiple_high=valuation_multiple_high,
        ),
    ]
    profit_low = min(scenario.profit_center for scenario in scenarios)
    profit_high = max(scenario.profit_center for scenario in scenarios)
    valuation_low = min(scenario.valuation_low for scenario in scenarios)
    valuation_high = max(scenario.valuation_high for scenario in scenarios)

    return OilGasBoundaryAnalysis(
        ticker=current.ticker,
        period=current.period,
        base_oil_price=base_oil_price,
        oil_price_floor=oil_price_floor,
        oil_price_ceiling=oil_price_ceiling,
        profit_sensitivity_per_usd=profit_sensitivity_per_usd,
        valuation_multiple_low=valuation_multiple_low,
        valuation_multiple_high=valuation_multiple_high,
        base_profit_ttm=base_profit_ttm,
        scenarios=scenarios,
        conclusion=(
            f"油价边界 {oil_price_floor:.2f}-{oil_price_ceiling:.2f}，"
            f"对应利润中枢 {profit_low:.2f}-{profit_high:.2f}，"
            f"估值边界 {valuation_low:.2f}-{valuation_high:.2f}。"
        ),
    )


def _append_non_recurring_check(
    record: QuarterRecord,
    issues: list[ValidationIssue],
) -> None:
    if (
        record.net_profit_parent is None
        or record.net_profit_deducted is None
        or record.non_recurring_gain_loss is None
    ):
        return

    implied_non_recurring = record.net_profit_parent - record.net_profit_deducted
    tolerance = max(1.0, abs(record.net_profit_parent) * 0.15)
    if abs(implied_non_recurring - record.non_recurring_gain_loss) > tolerance:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="non_recurring_reconciliation_gap",
                period=record.period,
                field="non_recurring_gain_loss",
                message=(
                    f"{record.period} 非经常性损益与归母/扣非差额不一致，"
                    "需回到原始披露校验。"
                ),
            )
        )


def _append_metric_checks(
    metric: QuarterMetrics,
    issues: list[ValidationIssue],
) -> None:
    if metric.revenue_yoy is not None and (metric.revenue_yoy > 1 or metric.revenue_yoy < -0.5):
        issues.append(
            ValidationIssue(
                severity="warning",
                code="extreme_revenue_yoy",
                period=metric.period,
                field="revenue_yoy",
                message=f"{metric.period} 收入同比波动极端，需核对口径或一次性因素。",
            )
        )

    if metric.ar_growth_gap_vs_revenue is not None and metric.ar_growth_gap_vs_revenue > 0.20:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="large_receivable_gap",
                period=metric.period,
                field="accounts_receivable",
                message=f"{metric.period} 应收增速显著高于收入增速，需验证收入质量。",
            )
        )


def _build_validation_report(issues: list[ValidationIssue]) -> DataValidationReport:
    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    status = "fail" if error_count else "warning" if warning_count else "pass"
    confidence_score = max(0.0, 1.0 - error_count * 0.35 - warning_count * 0.10)
    return DataValidationReport(
        status=status,
        confidence_score=round(confidence_score, 2),
        issues=issues,
    )


def _oil_gas_scenario(
    name: str,
    oil_price: float,
    base_oil_price: float,
    base_profit_ttm: float,
    profit_sensitivity_per_usd: float,
    valuation_multiple_low: float,
    valuation_multiple_high: float,
) -> OilGasScenario:
    profit_center = base_profit_ttm + (oil_price - base_oil_price) * profit_sensitivity_per_usd
    return OilGasScenario(
        name=name,
        oil_price=oil_price,
        profit_center=profit_center,
        valuation_low=profit_center * valuation_multiple_low,
        valuation_high=profit_center * valuation_multiple_high,
    )
