from fundamental_pulse.app.formatting import (
    build_history_table,
    build_result_kpis,
    build_watchlist_table,
    format_amount,
    format_date,
    format_error_summary,
    format_pct,
)
from fundamental_pulse.app.streamlit_app import parse_single_period_inputs
from fundamental_pulse.models import AnalysisRunResult, WatchlistRunItem, WatchlistRunResult


def test_formatting_helpers_standardize_pct_amount_and_date():
    assert format_pct(0.1234) == "12.34%"
    assert format_pct(None) == "NA"
    assert format_amount(12345678) == "1,234.57 万元"
    assert format_date("2026-05-05T17:55:07") == "2026-05-05 17:55"
    assert format_date(None) == "NA"


def test_result_kpis_use_formatted_values_and_no_advice_words():
    result = AnalysisRunResult(
        run_id="run-1",
        created_at="2026-05-05T17:55:07",
        ticker="300750.SZ",
        period="2025Q4",
        source="mock",
        report_path="reports/300750.SZ_2025Q4.md",
        classification="非经常性驱动",
        validation_status="pass",
        validation_confidence_score=1.0,
        highfreq_enabled=True,
        thesis_status="fail",
        report="本报告仅用于研究记录，不构成投资建议。",
    )

    kpis = build_result_kpis(result)

    assert kpis["报告期"] == "2025Q4"
    assert kpis["质量评分"] == "100.00%"
    assert kpis["数据源"] == "mock"
    assert "买入" not in str(kpis)
    assert "卖出" not in str(kpis)
    assert "目标价" not in str(kpis)


def test_history_and_watchlist_tables_are_structured():
    history = build_history_table(
        [
            {
                "created_at": "2026-05-05T17:55:07",
                "ticker": "300750.SZ",
                "period": "2025Q4",
                "source": "mock",
                "classification": "非经常性驱动",
                "validation_confidence_score": 1.0,
                "thesis_status": "fail",
            }
        ]
    )
    watchlist_table = build_watchlist_table(
        WatchlistRunResult(
            name="核心 A 股观察列表",
            total=1,
            succeeded=1,
            failed=0,
            items=[
                WatchlistRunItem(
                    ticker="300750.SZ",
                    name="宁德时代",
                    status="success",
                    period="2025Q4",
                    classification="非经常性驱动",
                    validation_confidence_score=1.0,
                    report_path="reports/300750.SZ_2025Q4.md",
                )
            ],
        )
    )

    assert history[0]["运行时间"] == "2026-05-05 17:55"
    assert history[0]["质量评分"] == "100.00%"
    assert watchlist_table[0]["状态"] == "success"
    assert watchlist_table[0]["质量评分"] == "100.00%"


def test_error_summary_is_short_with_details_separated():
    summary, detail = format_error_summary(
        "ticker mismatch between thesis ticker 300750.SZ and CLI ticker 600000.SH"
    )

    assert len(summary) <= 32
    assert "ticker" in detail


def test_parse_single_period_inputs_accepts_period_range():
    period, start, end = parse_single_period_inputs(
        period_text="2023Q1-2025Q4",
        start_text="",
        end_text="",
    )

    assert period is None
    assert start == "2023Q1"
    assert end == "2025Q4"


def test_parse_single_period_inputs_keeps_explicit_start_end():
    period, start, end = parse_single_period_inputs(
        period_text="2023Q1-2025Q4",
        start_text="2024Q1",
        end_text="2024Q4",
    )

    assert period is None
    assert start == "2024Q1"
    assert end == "2024Q4"
