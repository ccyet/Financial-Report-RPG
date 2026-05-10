import json
from pathlib import Path

from fundamental_pulse.models import AnalysisRequest, AnalysisRunResult
from fundamental_pulse.report_store import append_run_result, load_report_history, read_report
from fundamental_pulse.workflow import run_analysis


def test_run_analysis_mock_writes_report_and_index(tmp_path):
    result = run_analysis(
        AnalysisRequest(
            ticker="300750.SZ",
            source="mock",
            reports_dir=str(tmp_path),
        )
    )

    report_path = Path(result.report_path)
    index_path = tmp_path / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))

    assert isinstance(result, AnalysisRunResult)
    assert result.ticker == "300750.SZ"
    assert result.period == "2025Q4"
    assert report_path.exists()
    assert (tmp_path / "runs").exists()
    assert index["runs"][0]["run_id"] == result.run_id
    assert index["runs"][0]["report_path"] == result.report_path
    assert "不构成投资建议" in result.report
    assert "买入" not in result.report
    assert "卖出" not in result.report
    assert "目标价" not in result.report


def test_run_analysis_with_thesis_without_highfreq_keeps_product_usable(tmp_path):
    result = run_analysis(
        AnalysisRequest(
            ticker="300750.SZ",
            source="mock",
            thesis_file="examples/thesis/300750.yml",
            reports_dir=str(tmp_path),
        )
    )

    assert result.thesis_status == "unknown"
    assert result.highfreq_enabled is False
    assert "## 投资假设验证" in result.report
    assert "未提供高频经营信号" in result.report
    assert "不构成投资建议" in result.report


def test_report_store_appends_and_reads_history(tmp_path):
    result = AnalysisRunResult(
        run_id="run-1",
        created_at="2026-05-05T16:00:00",
        ticker="300750.SZ",
        period="2025Q4",
        source="mock",
        report_path=str(tmp_path / "300750.SZ_2025Q4.md"),
        archive_report_path=str(tmp_path / "runs" / "run-1_300750.SZ_2025Q4.md"),
        classification="收入驱动型增长",
        validation_status="pass",
        validation_confidence_score=1.0,
        highfreq_enabled=False,
        thesis_status=None,
        report="本报告仅用于研究记录，不构成投资建议。",
    )

    Path(result.report_path).write_text(result.report, encoding="utf-8")
    append_run_result(result, reports_dir=tmp_path)
    history = load_report_history(tmp_path)

    assert history[0]["run_id"] == "run-1"
    assert "report" not in history[0]
    assert read_report(result.report_path) == result.report


def test_streamlit_app_exposes_non_advice_disclaimer():
    from fundamental_pulse.app.streamlit_app import DISCLAIMER, format_history_label

    label = format_history_label(
        {
            "created_at": "2026-05-05T16:00:00",
            "ticker": "300750.SZ",
            "period": "2025Q4",
            "source": "mock",
            "classification": "非经常性驱动",
        }
    )

    assert "不构成投资建议" in DISCLAIMER
    assert "300750.SZ" in label
    assert "2025Q4" in label
    assert "买入" not in DISCLAIMER
    assert "卖出" not in DISCLAIMER
    assert "目标价" not in DISCLAIMER
