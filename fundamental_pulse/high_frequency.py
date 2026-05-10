from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import sqrt

from fundamental_pulse.models import (
    ForwardFactorSignal,
    ForwardOperatingOutlook,
    HighFrequencyCorrelation,
    HighFrequencyCorrelationReport,
    HighFrequencyObservation,
    QuarterMetrics,
)


class MockHighFrequencyFactorAdapter:
    def fetch_factor_observations(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
        factor_set: str | None = None,
    ) -> list[HighFrequencyObservation]:
        if factor_set not in (None, "auto", "catl"):
            raise ValueError(f"Unsupported factor set: {factor_set}.")

        observations = _catl_mock_observations(ticker)
        return [
            item
            for item in observations
            if (start is None or item.date >= start) and (end is None or item.date <= end)
        ]


def analyze_high_frequency_correlations(
    ticker: str,
    metrics: list[QuarterMetrics],
    observations: list[HighFrequencyObservation],
    target_metric: str = "revenue_yoy",
    max_lag_quarters: int = 1,
) -> HighFrequencyCorrelationReport:
    sorted_metrics = sorted(metrics, key=lambda item: item.period)
    target_by_period = {
        metric.period: getattr(metric, target_metric)
        for metric in sorted_metrics
        if getattr(metric, target_metric, None) is not None
    }
    period_order = [metric.period for metric in sorted_metrics]
    factor_values = _aggregate_factor_values_by_quarter(observations)

    correlations: list[HighFrequencyCorrelation] = []
    for (factor_name, factor_label), values_by_period in factor_values.items():
        for lag in range(max_lag_quarters + 1):
            paired = _paired_values(period_order, target_by_period, values_by_period, lag)
            if len(paired) < 3:
                continue
            factor_series = [item[0] for item in paired]
            target_series = [item[1] for item in paired]
            coefficient = _pearson(factor_series, target_series)
            if coefficient is None:
                continue
            correlations.append(
                _build_correlation(
                    factor_name=factor_name,
                    factor_label=factor_label,
                    target_metric=target_metric,
                    lag_quarters=lag,
                    correlation=coefficient,
                    observations=len(paired),
                )
            )

    correlations.sort(key=lambda item: abs(item.correlation), reverse=True)
    conclusion = _correlation_conclusion(correlations, target_metric)
    return HighFrequencyCorrelationReport(
        ticker=ticker,
        target_metric=target_metric,
        sample_size=len(target_by_period),
        correlations=correlations,
        conclusion=conclusion,
    )


def assess_next_quarter_outlook(
    ticker: str,
    current_period: str,
    correlation_report: HighFrequencyCorrelationReport,
    observations: list[HighFrequencyObservation],
    min_abs_correlation: float = 0.30,
) -> ForwardOperatingOutlook:
    forecast_period = _next_period(current_period)
    factor_values = _aggregate_factor_values_by_quarter(observations)
    best_correlations = _best_correlation_by_factor(correlation_report, min_abs_correlation)
    signals: list[ForwardFactorSignal] = []

    for factor_name, correlation in best_correlations.items():
        values_by_period = _find_factor_values(
            factor_values,
            factor_name=factor_name,
            factor_label=correlation.factor_label,
        )
        current_value = values_by_period.get(current_period)
        forecast_value = values_by_period.get(forecast_period)
        if current_value in (None, 0) or forecast_value is None:
            continue

        change_rate = forecast_value / current_value - 1
        expected_score = change_rate * _sign(correlation.correlation)
        signals.append(
            ForwardFactorSignal(
                factor_name=factor_name,
                factor_label=correlation.factor_label,
                current_period=current_period,
                forecast_period=forecast_period,
                current_value=current_value,
                forecast_value=forecast_value,
                change_rate=change_rate,
                correlation=correlation.correlation,
                expected_effect=_expected_effect(expected_score),
                rationale=_signal_rationale(correlation.factor_label, change_rate, expected_score),
            )
        )

    if not signals:
        return ForwardOperatingOutlook(
            ticker=ticker,
            current_period=current_period,
            forecast_period=forecast_period,
            target_metric=correlation_report.target_metric,
            outlook="数据不足",
            confidence_score=0.0,
            signals=[],
            risks=["缺少下一季度高频因子数据，无法形成前瞻判断。"],
            conclusion=f"{forecast_period} 高频数据不足，无法判断下一季度经营情况。",
        )

    weighted_scores = [
        signal.change_rate * _sign(signal.correlation) * abs(signal.correlation)
        for signal in signals
    ]
    net_score = sum(weighted_scores) / len(weighted_scores)
    outlook = "改善" if net_score > 0.02 else "走弱" if net_score < -0.02 else "平稳"
    confidence_score = round(
        min(1.0, sum(abs(signal.correlation) for signal in signals) / len(signals)),
        2,
    )
    risks = [signal.rationale for signal in signals if signal.expected_effect == "pressure"]

    return ForwardOperatingOutlook(
        ticker=ticker,
        current_period=current_period,
        forecast_period=forecast_period,
        target_metric=correlation_report.target_metric,
        outlook=outlook,
        confidence_score=confidence_score,
        signals=sorted(
            signals,
            key=lambda signal: abs(signal.change_rate * signal.correlation),
            reverse=True,
        ),
        risks=risks,
        conclusion=(
            f"下一季度 {forecast_period} 经营情况倾向{outlook}；"
            f"判断基于 {len(signals)} 个高频领先/同步因子，"
            f"综合信号强度 {net_score:.2%}。"
        ),
    )


def _aggregate_factor_values_by_quarter(
    observations: list[HighFrequencyObservation],
) -> dict[tuple[str, str], dict[str, float]]:
    grouped: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    labels: dict[str, str] = {}
    for item in observations:
        period = _date_to_period(item.date)
        grouped[(item.factor_name, item.factor_label)][period].append(item.value)
        labels[item.factor_name] = item.factor_label

    aggregated: dict[tuple[str, str], dict[str, float]] = {}
    for factor_key, values_by_period in grouped.items():
        aggregated[factor_key] = {
            period: sum(values) / len(values) for period, values in values_by_period.items()
        }
    return aggregated


def _best_correlation_by_factor(
    report: HighFrequencyCorrelationReport,
    min_abs_correlation: float,
) -> dict[str, HighFrequencyCorrelation]:
    best: dict[str, HighFrequencyCorrelation] = {}
    for item in report.correlations:
        if abs(item.correlation) < min_abs_correlation:
            continue
        existing = best.get(item.factor_name)
        if existing is None or abs(item.correlation) > abs(existing.correlation):
            best[item.factor_name] = item
    return best


def _find_factor_values(
    factor_values: dict[tuple[str, str], dict[str, float]],
    factor_name: str,
    factor_label: str,
) -> dict[str, float]:
    return factor_values.get((factor_name, factor_label), {})


def _paired_values(
    period_order: list[str],
    target_by_period: dict[str, float],
    values_by_period: dict[str, float],
    lag_quarters: int,
) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for index, period in enumerate(period_order):
        factor_index = index - lag_quarters
        if factor_index < 0:
            continue
        factor_period = period_order[factor_index]
        target = target_by_period.get(period)
        factor_value = values_by_period.get(factor_period)
        if target is not None and factor_value is not None:
            pairs.append((factor_value, target))
    return pairs


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    left_denominator = sqrt(sum((x - left_mean) ** 2 for x in left))
    right_denominator = sqrt(sum((y - right_mean) ** 2 for y in right))
    denominator = left_denominator * right_denominator
    if denominator == 0:
        return None
    return numerator / denominator


def _build_correlation(
    factor_name: str,
    factor_label: str,
    target_metric: str,
    lag_quarters: int,
    correlation: float,
    observations: int,
) -> HighFrequencyCorrelation:
    direction = "positive" if correlation > 0.2 else "negative" if correlation < -0.2 else "neutral"
    lag_text = "同步" if lag_quarters == 0 else f"领先 {lag_quarters} 个季度"
    direction_text = {"positive": "正相关", "negative": "负相关", "neutral": "相关性较弱"}[
        direction
    ]
    return HighFrequencyCorrelation(
        factor_name=factor_name,
        factor_label=factor_label,
        target_metric=target_metric,
        lag_quarters=lag_quarters,
        correlation=correlation,
        observations=observations,
        direction=direction,
        interpretation=f"{factor_label}与{target_metric}{lag_text}{direction_text}。",
    )


def _correlation_conclusion(
    correlations: list[HighFrequencyCorrelation],
    target_metric: str,
) -> str:
    if not correlations:
        return f"样本不足，无法判断高频因子与 {target_metric} 的相关性。"
    top = correlations[0]
    return (
        f"{top.factor_label}与{target_metric}相关性最高，"
        f"相关系数 {top.correlation:.2f}，{top.interpretation}"
    )


def _date_to_period(value: str) -> str:
    parsed = date.fromisoformat(value)
    quarter = (parsed.month - 1) // 3 + 1
    return f"{parsed.year}Q{quarter}"


def _next_period(period: str) -> str:
    year = int(period[:4])
    quarter = int(period[5])
    if quarter == 4:
        return f"{year + 1}Q1"
    return f"{year}Q{quarter + 1}"


def _sign(value: float) -> int:
    return 1 if value >= 0 else -1


def _expected_effect(score: float) -> str:
    if score > 0.03:
        return "support"
    if score < -0.03:
        return "pressure"
    return "neutral"


def _signal_rationale(factor_label: str, change_rate: float, expected_score: float) -> str:
    direction = "上行" if change_rate > 0 else "下行" if change_rate < 0 else "持平"
    effect = (
        "支撑"
        if expected_score > 0.03
        else "形成压力"
        if expected_score < -0.03
        else "影响中性"
    )
    return f"{factor_label}{direction} {change_rate:.2%}，对目标指标{effect}。"


def _catl_mock_observations(ticker: str) -> list[HighFrequencyObservation]:
    factor_rows = {
        "china_nev_sales": ("新能源汽车销量", [52, 58, 66, 78, 95, 80, 86, 82, 90]),
        "power_battery_installation": ("动力电池装机量", [28, 32, 36, 44, 125, 105, 115, 110, 122]),
        "lithium_carbonate_price": ("碳酸锂价格", [220, 205, 190, 170, 150, 152, 149, 151, 158]),
        "battery_export_volume": ("动力电池出口量", [7, 8, 9, 11, 17, 14, 15, 14.5, 16]),
    }
    quarter_dates = [
        "2024-01-31",
        "2024-04-30",
        "2024-07-31",
        "2024-10-31",
        "2025-01-31",
        "2025-04-30",
        "2025-07-31",
        "2025-10-31",
        "2026-01-31",
    ]
    observations: list[HighFrequencyObservation] = []
    for factor_name, (factor_label, values) in factor_rows.items():
        for factor_date, value in zip(quarter_dates, values, strict=True):
            observations.append(
                HighFrequencyObservation(
                    ticker=ticker,
                    factor_name=factor_name,
                    factor_label=factor_label,
                    date=factor_date,
                    value=value,
                    frequency="monthly",
                )
            )
    return observations
