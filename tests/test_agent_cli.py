from pathlib import Path

from financial_report_rpg.agent_cli import run_command
from financial_report_rpg.rpg import default_journey, load_progress


def test_agent_cli_records_note_and_exports_reports(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"

    output = run_command(
        [
            "note",
            "--text",
            "先记录收入结构的第一条假设。",
            "--tag",
            "收入",
            "--task",
            "mdna",
        ],
        progress_path=progress_path,
        report_dir=report_dir,
    )

    progress = load_progress(progress_path, default_journey())
    assert "已记录" in output
    assert progress.notes[0].text == "先记录收入结构的第一条假设。"
    assert (report_dir / "progress.md").exists()
    assert (report_dir / "progress.html").exists()


def test_agent_cli_can_complete_task_with_note(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"

    run_command(
        ["complete-task", "cash", "--note", "现金流副本已完成。"],
        progress_path=progress_path,
        report_dir=report_dir,
    )

    progress = load_progress(progress_path, default_journey())
    assert progress.completed_tasks == {"cash"}
    assert progress.notes[0].linked_task_id == "cash"
