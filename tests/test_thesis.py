import json

import pytest

from fundamental_pulse.models import QuarterMetrics
from fundamental_pulse.thesis import (
    ThesisValidationError,
    load_thesis,
    verify_thesis,
)


def test_load_thesis_from_json(tmp_path):
    thesis_path = tmp_path / "thesis.json"
    thesis_path.write_text(
        json.dumps(
            {
                "ticker": "300750.SZ",
                "name": "宁德时代季度经营假设",
                "drivers": [
                    {
                        "id": "revenue_growth",
                        "name": "收入增速",
                        "metric": "revenue_yoy",
                        "operator": ">=",
                        "threshold": 0.1,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    thesis = load_thesis(thesis_path)

    assert thesis.ticker == "300750.SZ"
    assert thesis.drivers[0].id == "revenue_growth"


def test_load_thesis_from_yaml():
    thesis = load_thesis("examples/thesis/300750.yml")

    assert thesis.ticker == "300750.SZ"
    assert len(thesis.drivers) >= 4


def test_verify_thesis_metric_and_highfreq_drivers():
    thesis = load_thesis("examples/thesis/300750.yml")
    metrics = QuarterMetrics(
        ticker="300750.SZ",
        period="2025Q4",
        revenue_yoy=0.30,
        deducted_np_yoy=0.25,
        gross_margin_delta_yoy=0.03,
        ocf_to_np=1.2,
    )
    highfreq_summary = {
        "revenue_side": "positive",
        "cost_side": "positive",
        "margin_side": "neutral",
        "cashflow_side": "negative",
        "risk_side": "negative",
    }

    result = verify_thesis(
        thesis=thesis,
        ticker="300750.SZ",
        metrics=metrics,
        highfreq_summary=highfreq_summary,
    )

    assert result.ticker == "300750.SZ"
    assert result.period == "2025Q4"
    assert result.summary_status == "fail"
    assert {driver.id: driver.status for driver in result.drivers}["revenue_growth"] == "pass"
    assert {driver.id: driver.status for driver in result.drivers}["cashflow_quality"] == "pass"
    assert {driver.id: driver.status for driver in result.drivers}["highfreq_cashflow"] == "fail"


def test_verify_thesis_highfreq_missing_is_unknown_not_failure():
    thesis = load_thesis("examples/thesis/300750.yml")
    metrics = QuarterMetrics(
        ticker="300750.SZ",
        period="2025Q4",
        revenue_yoy=0.30,
        deducted_np_yoy=0.25,
        gross_margin_delta_yoy=0.03,
        ocf_to_np=1.2,
    )

    result = verify_thesis(
        thesis=thesis,
        ticker="300750.SZ",
        metrics=metrics,
        highfreq_summary=None,
    )

    assert result.summary_status == "unknown"
    assert {driver.id: driver.status for driver in result.drivers}["highfreq_revenue"] == "unknown"


def test_verify_thesis_ticker_mismatch_raises():
    thesis = load_thesis("examples/thesis/300750.yml")

    with pytest.raises(ThesisValidationError, match="ticker"):
        verify_thesis(
            thesis=thesis,
            ticker="600000.SH",
            metrics=QuarterMetrics(ticker="600000.SH", period="2025Q4"),
            highfreq_summary=None,
        )
