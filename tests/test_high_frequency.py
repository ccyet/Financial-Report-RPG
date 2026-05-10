import pytest

from fundamental_pulse.high_frequency import (
    MockHighFrequencyFactorAdapter,
    analyze_high_frequency_correlations,
    assess_next_quarter_outlook,
)
from fundamental_pulse.models import (
    HighFrequencyCorrelation,
    HighFrequencyCorrelationReport,
    HighFrequencyObservation,
    QuarterMetrics,
)


def test_mock_high_frequency_adapter_uses_catl_relevant_factors_not_oil():
    observations = MockHighFrequencyFactorAdapter().fetch_factor_observations("300750.SZ")
    factor_names = {item.factor_name for item in observations}

    assert "china_nev_sales" in factor_names
    assert "power_battery_installation" in factor_names
    assert "lithium_carbonate_price" in factor_names
    assert "brent_oil_price" not in factor_names


def test_analyze_high_frequency_correlations_ranks_company_specific_factors():
    metrics = [
        QuarterMetrics(ticker="300750.SZ", period="2024Q1", revenue_yoy=0.10),
        QuarterMetrics(ticker="300750.SZ", period="2024Q2", revenue_yoy=0.20),
        QuarterMetrics(ticker="300750.SZ", period="2024Q3", revenue_yoy=0.30),
        QuarterMetrics(ticker="300750.SZ", period="2024Q4", revenue_yoy=0.40),
    ]
    observations = [
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="power_battery_installation",
            factor_label="动力电池装机量",
            date="2024-01-31",
            value=10,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="power_battery_installation",
            factor_label="动力电池装机量",
            date="2024-04-30",
            value=20,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="power_battery_installation",
            factor_label="动力电池装机量",
            date="2024-07-31",
            value=30,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="power_battery_installation",
            factor_label="动力电池装机量",
            date="2024-10-31",
            value=40,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="lithium_carbonate_price",
            factor_label="碳酸锂价格",
            date="2024-01-31",
            value=40,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="lithium_carbonate_price",
            factor_label="碳酸锂价格",
            date="2024-04-30",
            value=30,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="lithium_carbonate_price",
            factor_label="碳酸锂价格",
            date="2024-07-31",
            value=20,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="lithium_carbonate_price",
            factor_label="碳酸锂价格",
            date="2024-10-31",
            value=10,
            frequency="monthly",
        ),
    ]

    report = analyze_high_frequency_correlations(
        ticker="300750.SZ",
        metrics=metrics,
        observations=observations,
        target_metric="revenue_yoy",
        max_lag_quarters=0,
    )

    assert report.target_metric == "revenue_yoy"
    assert report.correlations[0].factor_name == "power_battery_installation"
    assert report.correlations[0].correlation == pytest.approx(1.0)
    assert report.correlations[1].factor_name == "lithium_carbonate_price"
    assert report.correlations[1].correlation == pytest.approx(-1.0)
    assert "动力电池装机量" in report.conclusion


def test_assess_next_quarter_outlook_uses_future_factor_trends():
    correlation_report = HighFrequencyCorrelationReport(
        ticker="300750.SZ",
        target_metric="revenue_yoy",
        sample_size=4,
        correlations=[
            HighFrequencyCorrelation(
                factor_name="power_battery_installation",
                factor_label="动力电池装机量",
                target_metric="revenue_yoy",
                lag_quarters=0,
                correlation=0.90,
                observations=4,
                direction="positive",
                interpretation="动力电池装机量与收入同比同步正相关。",
            ),
            HighFrequencyCorrelation(
                factor_name="lithium_carbonate_price",
                factor_label="碳酸锂价格",
                target_metric="revenue_yoy",
                lag_quarters=0,
                correlation=-0.80,
                observations=4,
                direction="negative",
                interpretation="碳酸锂价格与收入同比同步负相关。",
            ),
        ],
        conclusion="动力电池装机量与收入同比相关性最高。",
    )
    observations = [
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="power_battery_installation",
            factor_label="动力电池装机量",
            date="2025-10-31",
            value=100,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="power_battery_installation",
            factor_label="动力电池装机量",
            date="2026-01-31",
            value=115,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="lithium_carbonate_price",
            factor_label="碳酸锂价格",
            date="2025-10-31",
            value=150,
            frequency="monthly",
        ),
        HighFrequencyObservation(
            ticker="300750.SZ",
            factor_name="lithium_carbonate_price",
            factor_label="碳酸锂价格",
            date="2026-01-31",
            value=165,
            frequency="monthly",
        ),
    ]

    outlook = assess_next_quarter_outlook(
        ticker="300750.SZ",
        current_period="2025Q4",
        correlation_report=correlation_report,
        observations=observations,
    )

    assert outlook.forecast_period == "2026Q1"
    assert outlook.outlook == "改善"
    assert outlook.confidence_score > 0
    assert outlook.signals[0].factor_name == "power_battery_installation"
    assert outlook.signals[0].expected_effect == "support"
    assert outlook.signals[1].expected_effect == "pressure"
    assert "下一季度" in outlook.conclusion


def test_assess_next_quarter_outlook_returns_insufficient_when_future_data_missing():
    correlation_report = HighFrequencyCorrelationReport(
        ticker="300750.SZ",
        target_metric="revenue_yoy",
        sample_size=4,
        correlations=[
            HighFrequencyCorrelation(
                factor_name="power_battery_installation",
                factor_label="动力电池装机量",
                target_metric="revenue_yoy",
                lag_quarters=0,
                correlation=0.90,
                observations=4,
                direction="positive",
                interpretation="动力电池装机量与收入同比同步正相关。",
            )
        ],
        conclusion="动力电池装机量与收入同比相关性最高。",
    )

    outlook = assess_next_quarter_outlook(
        ticker="300750.SZ",
        current_period="2025Q4",
        correlation_report=correlation_report,
        observations=[],
    )

    assert outlook.outlook == "数据不足"
    assert outlook.signals == []
