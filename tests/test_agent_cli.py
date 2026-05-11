from pathlib import Path
from types import SimpleNamespace

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


def test_agent_cli_guides_and_completes_chapter_check_ins(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"

    guide = run_command(["next"], progress_path=progress_path, report_dir=report_dir)
    assert "当前关卡：初始印象" in guide
    assert "通关标准" in guide

    run_command(
        ["complete-chapter", "first_impression", "--note", "已写下第一判断。"],
        progress_path=progress_path,
        report_dir=report_dir,
    )

    progress = load_progress(progress_path, default_journey())
    assert progress.completed_chapters == {"first_impression"}
    assert progress.notes[0].linked_chapter_id == "first_impression"
    assert progress.notes[0].linked_task_id is None


def test_agent_cli_start_guides_from_saved_progress_and_dungeon(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"

    output = run_command(
        ["start", "--dungeon", "半导体矿洞"],
        progress_path=progress_path,
        report_dir=report_dir,
    )

    progress = load_progress(progress_path, default_journey())
    assert progress.active_dungeon == "半导体矿洞"
    assert "读取存档" in output
    assert "等级 1/175" in output
    assert "本次挑战副本：半导体矿洞" in output
    assert "副本进度：主线 0/50" in output
    assert "确认本次是否挑战该副本" in output
    assert ".local" not in output
    assert "progress.html" not in output


def test_agent_cli_completion_is_immersive_and_hides_storage_paths(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"

    output = run_command(
        ["complete-chapter", "first_impression", "--note", "第一关完成。"],
        progress_path=progress_path,
        report_dir=report_dir,
    )

    assert "关卡结算" in output
    assert "等级 2/175" in output
    assert "主线 1/50" in output
    assert "若当前终端支持图片" in output
    assert ".local" not in output
    assert "progress.html" not in output


def test_agent_cli_export_hides_storage_paths(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"

    output = run_command(["export"], progress_path=progress_path, report_dir=report_dir)

    assert "已导出" in output
    assert "报告：" not in output
    assert str(report_dir) not in output
    assert "progress.md" not in output
    assert "progress.html" not in output


def test_agent_cli_download_reports_returns_game_message_without_paths(tmp_path: Path):
    class FakeDownloadClient:
        def download_company_documents(self, company, *, from_year, output_dir):
            assert company == "300750"
            assert from_year == 2022
            assert output_dir == tmp_path / "reports"
            return SimpleNamespace(
                security=SimpleNamespace(code="300750", name="宁德时代"),
                from_year=2022,
                prospectus_count=1,
                financial_report_count=4,
                downloaded_count=5,
                skipped_count=0,
                failed_count=0,
                failures=[],
            )

    output = run_command(
        ["download-reports", "300750", "--output-dir", str(tmp_path / "reports")],
        progress_path=tmp_path / "progress.json",
        report_dir=tmp_path / "exports",
        cninfo_client=FakeDownloadClient(),
    )

    assert "资料背包更新" in output
    assert "宁德时代（300750）" in output
    assert "招股说明书 1 份" in output
    assert "2022年至今财报 4 份" in output
    assert str(tmp_path) not in output
    assert "progress.html" not in output


def test_agent_cli_keeps_progress_separate_by_industry_dungeon(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"

    run_command(
        ["start", "--dungeon", "动力电池峡谷"],
        progress_path=progress_path,
        report_dir=report_dir,
    )
    run_command(
        ["complete-chapter", "first_impression", "--note", "电池副本第一关完成。"],
        progress_path=progress_path,
        report_dir=report_dir,
    )
    semiconductor_start = run_command(
        ["start", "--dungeon", "半导体矿洞"],
        progress_path=progress_path,
        report_dir=report_dir,
    )
    battery_start = run_command(
        ["start", "--dungeon", "动力电池峡谷"],
        progress_path=progress_path,
        report_dir=report_dir,
    )

    assert "本次挑战副本：半导体矿洞" in semiconductor_start
    assert "副本进度：主线 0/50" in semiconductor_start
    assert "当前关卡：初始印象" in semiconductor_start
    assert "本次挑战副本：动力电池峡谷" in battery_start
    assert "副本进度：主线 1/50" in battery_start
    assert "当前关卡：收入结构" in battery_start
