from pathlib import Path

from financial_report_rpg.agent_journal import (
    build_notion_export,
    complete_chapter,
    generate_html_report,
    generate_text_report,
    next_check_in,
    record_note,
    save_reports,
)
from financial_report_rpg.rpg import (
    RpgProgress,
    default_journey,
    load_progress,
    save_progress,
    toggle_boss,
    toggle_task,
)


def test_conversation_note_persists_with_progress(tmp_path: Path):
    journey = default_journey()
    progress = record_note(
        RpgProgress(),
        text="宁德时代现金流比利润更值得先核对。",
        tags=["现金流", "宁德时代"],
        linked_task_id="cash",
        journey=journey,
        created_at="2026-05-10T12:00:00+08:00",
    )
    path = tmp_path / "progress.json"

    save_progress(progress, path)
    loaded = load_progress(path, journey)

    assert loaded.notes[0].text == "宁德时代现金流比利润更值得先核对。"
    assert loaded.notes[0].tags == ["现金流", "宁德时代"]
    assert loaded.notes[0].linked_task_id == "cash"


def test_reports_include_current_progress_notes_and_no_user_inputs():
    journey = default_journey()
    progress = toggle_task(RpgProgress(), "cash", journey)
    progress = toggle_boss(progress, "three_year_map", journey)
    progress = record_note(
        progress,
        text="先把应收、存货和经营现金流放进一张地图。",
        tags=["地图"],
        journey=journey,
        created_at="2026-05-10T12:00:00+08:00",
    )

    text_report = generate_text_report(progress, journey)
    html_report = generate_html_report(progress, journey)

    assert "Lv.1 财报新兵" in text_report
    assert "三年财报地图" in text_report
    assert "先把应收、存货和经营现金流放进一张地图。" in text_report
    assert "<!doctype html>" in html_report.lower()
    assert "先把应收、存货和经营现金流放进一张地图。" in html_report
    assert "<input" not in html_report.lower()
    assert "<textarea" not in html_report.lower()
    assert "当前关卡" in text_report
    assert "通关标准" in html_report


def test_next_check_in_guides_chapter_by_chapter():
    journey = default_journey()
    progress = RpgProgress()

    first_gate = next_check_in(progress, journey)
    assert first_gate.kind == "chapter"
    assert first_gate.id == "first_impression"
    assert "第一判断" in first_gate.prompt
    assert first_gate.completion_command == "complete-chapter first_impression"

    progress = complete_chapter(progress, "first_impression", journey)
    second_gate = next_check_in(progress, journey)
    assert second_gate.kind == "chapter"
    assert second_gate.id == "revenue_structure"
    assert "收入" in second_gate.title


def test_next_check_in_falls_back_to_daily_tasks_after_chapters():
    journey = default_journey()
    progress = RpgProgress(completed_chapters={chapter.id for chapter in journey.chapters})

    gate = next_check_in(progress, journey)

    assert gate.kind == "daily_task"
    assert gate.id == "mdna"
    assert "管理层讨论" in gate.title


def test_save_reports_writes_text_and_html(tmp_path: Path):
    journey = default_journey()
    progress = record_note(
        RpgProgress(),
        text="把第一印象留作后续验证对象。",
        journey=journey,
        created_at="2026-05-10T12:00:00+08:00",
    )

    text_path, html_path = save_reports(progress, journey, tmp_path)

    assert text_path.read_text(encoding="utf-8").startswith("# 财报 RPG 当前进度")
    assert "把第一印象留作后续验证对象。" in html_path.read_text(encoding="utf-8")


def test_notion_export_is_connector_ready():
    journey = default_journey()
    progress = record_note(
        RpgProgress(),
        text="需要在产业链里确认国产替代位置。",
        tags=["Notion"],
        journey=journey,
        created_at="2026-05-10T12:00:00+08:00",
    )

    payload = build_notion_export(progress, journey)

    assert payload["title"] == "财报 RPG 当前进度"
    assert payload["properties"]["level"] == "Lv.1 财报新兵"
    assert payload["properties"]["daily_completed"] == 0
    assert "需要在产业链里确认国产替代位置。" in payload["markdown"]
