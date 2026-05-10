from __future__ import annotations

from fundamental_pulse.models import (
    GrowthClassification,
    ProfitAttribution,
    QuarterMetrics,
    QuarterRecord,
)

DIFFERENCE_FIELDS = (
    "revenue",
    "operating_cost",
    "selling_expense",
    "admin_expense",
    "rd_expense",
    "financial_expense",
    "net_profit_parent",
    "net_profit_deducted",
    "non_recurring_gain_loss",
    "operating_cash_flow",
)

EXPENSE_FIELDS = ("selling_expense", "admin_expense", "rd_expense", "financial_expense")


def normalize_to_single_quarter(records: list[QuarterRecord]) -> list[QuarterRecord]:
    sorted_records = sorted(records, key=lambda record: (record.ticker, _period_key(record.period)))
    previous_cumulative_by_year: dict[tuple[str, int], QuarterRecord] = {}
    normalized: list[QuarterRecord] = []

    for record in sorted_records:
        year, quarter = _period_key(record.period)
        if not record.is_cumulative:
            normalized.append(record.model_copy(update={"is_cumulative": False}))
            continue

        updates: dict[str, float | bool | None] = {"is_cumulative": False}
        previous = previous_cumulative_by_year.get((record.ticker, year))
        for field in DIFFERENCE_FIELDS:
            value = getattr(record, field)
            if quarter == 1:
                updates[field] = value
            elif previous is None:
                updates[field] = None
            else:
                previous_value = getattr(previous, field)
                updates[field] = _subtract_optional(value, previous_value)

        normalized.append(record.model_copy(update=updates))
        previous_cumulative_by_year[(record.ticker, year)] = record

    return normalized


def calculate_metrics(records: list[QuarterRecord]) -> list[QuarterMetrics]:
    sorted_records = sorted(records, key=lambda record: (record.ticker, _period_key(record.period)))
    by_key = {(record.ticker, record.period): record for record in sorted_records}
    metrics: list[QuarterMetrics] = []

    for record in sorted_records:
        year, quarter = _period_key(record.period)
        previous_year = by_key.get((record.ticker, f"{year - 1}Q{quarter}"))
        previous_quarter = by_key.get((record.ticker, _previous_period(year, quarter)))

        revenue_yoy = _growth(record.revenue, previous_year.revenue if previous_year else None)
        gross_margin = _gross_margin(record)
        expense_ratio = _expense_ratio(record)

        previous_year_gross_margin = _gross_margin(previous_year) if previous_year else None
        previous_year_expense_ratio = _expense_ratio(previous_year) if previous_year else None

        ar_growth_yoy = _growth(
            record.accounts_receivable,
            previous_year.accounts_receivable if previous_year else None,
        )
        inventory_growth_yoy = _growth(
            record.inventory,
            previous_year.inventory if previous_year else None,
        )

        metrics.append(
            QuarterMetrics(
                ticker=record.ticker,
                period=record.period,
                revenue_yoy=revenue_yoy,
                revenue_qoq=_growth(
                    record.revenue,
                    previous_quarter.revenue if previous_quarter else None,
                ),
                deducted_np_yoy=_growth(
                    record.net_profit_deducted,
                    previous_year.net_profit_deducted if previous_year else None,
                ),
                deducted_np_qoq=_growth(
                    record.net_profit_deducted,
                    previous_quarter.net_profit_deducted if previous_quarter else None,
                ),
                gross_margin=gross_margin,
                gross_margin_delta_yoy=_subtract_optional(gross_margin, previous_year_gross_margin),
                expense_ratio=expense_ratio,
                expense_ratio_delta_yoy=_subtract_optional(
                    expense_ratio,
                    previous_year_expense_ratio,
                ),
                ocf_to_np=_safe_div(record.operating_cash_flow, record.net_profit_parent),
                non_recurring_ratio=_safe_div(
                    abs(record.non_recurring_gain_loss)
                    if record.non_recurring_gain_loss is not None
                    else None,
                    abs(record.net_profit_parent) if record.net_profit_parent is not None else None,
                ),
                ar_growth_gap_vs_revenue=_subtract_optional(ar_growth_yoy, revenue_yoy),
                inventory_growth_gap_vs_revenue=_subtract_optional(
                    inventory_growth_yoy,
                    revenue_yoy,
                ),
            )
        )

    return metrics


def classify_growth(metrics: QuarterMetrics) -> GrowthClassification:
    required_fields = ("revenue_yoy", "deducted_np_yoy", "gross_margin_delta_yoy")
    missing_fields = [field for field in required_fields if getattr(metrics, field) is None]
    if missing_fields:
        return GrowthClassification(
            growth_type="数据不足",
            explanation=f"缺少关键指标：{', '.join(missing_fields)}，无法判断增长性质。",
            triggered_rules=["数据不足"],
            missing_fields=missing_fields,
        )

    revenue_yoy = metrics.revenue_yoy
    deducted_np_yoy = metrics.deducted_np_yoy
    gross_margin_delta_yoy = metrics.gross_margin_delta_yoy
    assert revenue_yoy is not None
    assert deducted_np_yoy is not None
    assert gross_margin_delta_yoy is not None

    if metrics.non_recurring_ratio is not None and metrics.non_recurring_ratio > 0.30:
        return _classification("非经常性驱动", "非经常性损益占归母净利润比例超过 30%。")

    if deducted_np_yoy > 0.15 and metrics.ocf_to_np is not None and metrics.ocf_to_np < 0.50:
        return _classification(
            "利润增长但现金流背离",
            "扣非净利润同比增长超过 15%，但经营现金流/归母净利润低于 0.50。",
        )

    if revenue_yoy > 0.15 and deducted_np_yoy > 0.10 and gross_margin_delta_yoy > -0.02:
        return _classification(
            "收入驱动型增长",
            "收入同比增长超过 15%，扣非净利润同比增长超过 10%，毛利率未明显恶化。",
        )

    if revenue_yoy < 0.15 and deducted_np_yoy > 0.20 and gross_margin_delta_yoy > 0.02:
        return _classification(
            "毛利率改善型利润增长",
            "收入同比增长低于 15%，扣非净利润同比增长超过 20%，"
            "毛利率同比改善超过 2 个百分点。",
        )

    if (
        revenue_yoy < 0.10
        and deducted_np_yoy > 0.15
        and metrics.expense_ratio_delta_yoy is not None
        and metrics.expense_ratio_delta_yoy < -0.02
    ):
        return _classification(
            "费用压缩型利润增长",
            "收入同比增长低于 10%，扣非净利润同比增长超过 15%，"
            "费用率同比下降超过 2 个百分点。",
        )

    if revenue_yoy > 0.15 and deducted_np_yoy < 0.05:
        return _classification(
            "收入增长但利润恶化",
            "收入同比增长超过 15%，但扣非净利润同比增长低于 5%。",
        )

    if metrics.ar_growth_gap_vs_revenue is not None and metrics.ar_growth_gap_vs_revenue > 0.10:
        return _classification(
            "营运资本风险型增长",
            "应收账款同比增速高于收入同比增速 10 个百分点以上。",
        )

    if (
        metrics.inventory_growth_gap_vs_revenue is not None
        and metrics.inventory_growth_gap_vs_revenue > 0.10
    ):
        return _classification(
            "营运资本风险型增长",
            "存货同比增速高于收入同比增速 10 个百分点以上。",
        )

    return _classification("中性或待判断", "未触发明确增长性质规则。")


def attribute_profit_growth(
    current: QuarterRecord,
    previous_same_quarter: QuarterRecord,
) -> ProfitAttribution:
    previous_gross_margin = _gross_margin(previous_same_quarter)
    current_gross_margin = _gross_margin(current)
    current_expenses = _sum_optional(*(getattr(current, field) for field in EXPENSE_FIELDS))
    previous_expenses = _sum_optional(
        *(getattr(previous_same_quarter, field) for field in EXPENSE_FIELDS)
    )

    revenue_delta = _subtract_optional(current.revenue, previous_same_quarter.revenue)
    gross_margin_delta = _subtract_optional(current_gross_margin, previous_gross_margin)

    contributions = {
        "收入贡献": _multiply_optional(revenue_delta, previous_gross_margin),
        "毛利率贡献": _multiply_optional(current.revenue, gross_margin_delta),
        "费用贡献": _subtract_optional(previous_expenses, current_expenses),
        "非经常性损益贡献": _subtract_optional(
            current.non_recurring_gain_loss,
            previous_same_quarter.non_recurring_gain_loss,
        ),
    }

    return ProfitAttribution(
        ticker=current.ticker,
        period=current.period,
        profit_delta=_subtract_optional(
            current.net_profit_deducted,
            previous_same_quarter.net_profit_deducted,
        ),
        revenue_contribution=contributions["收入贡献"],
        gross_margin_contribution=contributions["毛利率贡献"],
        expense_contribution=contributions["费用贡献"],
        non_recurring_contribution=contributions["非经常性损益贡献"],
        top_positive=_top_contributions(contributions, positive=True),
        top_negative=_top_contributions(contributions, positive=False),
    )


def _period_key(period: str) -> tuple[int, int]:
    if len(period) != 6 or period[4] != "Q":
        raise ValueError(f"Invalid period: {period}. Expected YYYYQ1-YYYYQ4.")
    year = int(period[:4])
    quarter = int(period[5])
    if quarter not in {1, 2, 3, 4}:
        raise ValueError(f"Invalid period: {period}. Expected YYYYQ1-YYYYQ4.")
    return year, quarter


def _previous_period(year: int, quarter: int) -> str:
    if quarter == 1:
        return f"{year - 1}Q4"
    return f"{year}Q{quarter - 1}"


def _subtract_optional(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _multiply_optional(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left * right


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _growth(current: float | None, previous: float | None) -> float | None:
    ratio = _safe_div(current, previous)
    if ratio is None:
        return None
    return ratio - 1


def _gross_margin(record: QuarterRecord | None) -> float | None:
    if record is None:
        return None
    gross_profit = _subtract_optional(record.revenue, record.operating_cost)
    return _safe_div(gross_profit, record.revenue)


def _expense_ratio(record: QuarterRecord | None) -> float | None:
    if record is None:
        return None
    return _safe_div(
        _sum_optional(*(getattr(record, field) for field in EXPENSE_FIELDS)),
        record.revenue,
    )


def _sum_optional(*values: float | None) -> float | None:
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _classification(growth_type: str, reason: str) -> GrowthClassification:
    return GrowthClassification(
        growth_type=growth_type,
        explanation=f"触发规则：{growth_type}。{reason}",
        triggered_rules=[growth_type],
    )


def _top_contributions(contributions: dict[str, float | None], positive: bool) -> list[str]:
    filtered = [
        (name, value)
        for name, value in contributions.items()
        if value is not None and ((positive and value > 0) or (not positive and value < 0))
    ]
    filtered.sort(key=lambda item: abs(item[1]), reverse=True)
    return [name for name, _ in filtered[:2]]
