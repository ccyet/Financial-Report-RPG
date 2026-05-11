from pathlib import Path
from types import SimpleNamespace

from financial_report_rpg.agent_cli import run_command
from financial_report_rpg.cninfo import CninfoClient, CninfoError
from financial_report_rpg.rpg import default_journey, load_progress
from tests.test_cninfo import FakeCninfoFetch


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


def test_download_list_panel_flow_binds_docs_to_current_dungeon(tmp_path: Path):
    progress_path = tmp_path / "progress.json"
    report_dir = tmp_path / "exports"
    docs_dir = tmp_path / "reports"
    client = CninfoClient(fetch=FakeCninfoFetch())

    run_command(
        ["start", "--dungeon", "动力电池峡谷"],
        progress_path=progress_path,
        report_dir=report_dir,
    )
    download_output = run_command(
        ["download-reports", "300750", "--output-dir", str(docs_dir)],
        progress_path=progress_path,
        report_dir=report_dir,
        cninfo_client=client,
    )
    docs_output = run_command(
        ["list-docs", "300750", "--output-dir", str(docs_dir)],
        progress_path=progress_path,
        report_dir=report_dir,
    )
    run_command(
        ["complete-chapter", "first_impression", "--note", "第一关完成。"],
        progress_path=progress_path,
        report_dir=report_dir,
    )
    panel_output = run_command(["panel"], progress_path=progress_path, report_dir=report_dir)
    battery_status = run_command(["status"], progress_path=progress_path, report_dir=report_dir)
    run_command(
        ["start", "--dungeon", "半导体矿洞"],
        progress_path=progress_path,
        report_dir=report_dir,
    )
    semiconductor_status = run_command(
        ["status"], progress_path=progress_path, report_dir=report_dir
    )

    assert "资料背包更新" in download_output
    assert "宁德时代：招股书 1，财报 4" in battery_status
    assert "资料背包：宁德时代：招股书 1，财报 4" in panel_output
    assert "最近记录：第一关完成。" in panel_output
    assert "资料清单：宁德时代（300750）" in docs_output
    assert "年度报告" in docs_output
    assert "三季度报告" in docs_output
    assert "宁德时代" not in semiconductor_status
    for output in [
        download_output,
        docs_output,
        panel_output,
        battery_status,
        semiconductor_status,
    ]:
        assert str(tmp_path) not in output
        assert "manifest.json" not in output
        assert ".pdf" not in output


def test_agent_cli_doctor_reports_ready_and_failures(tmp_path: Path):
    class ReadyClient:
        def ping(self):
            return None

    ready_output = run_command(
        ["doctor"],
        progress_path=tmp_path / "progress.json",
        report_dir=tmp_path / "exports",
        cninfo_client=ReadyClient(),
        repo_root=Path.cwd(),
    )
    bad_progress = tmp_path / "bad.json"
    bad_progress.write_text("{bad json", encoding="utf-8")

    class BrokenClient:
        def ping(self):
            raise CninfoError("巨潮不可达")

    failure_output = run_command(
        ["doctor"],
        progress_path=bad_progress,
        report_dir=tmp_path / "exports",
        cninfo_client=BrokenClient(),
        repo_root=tmp_path,
    )

    assert "诊断面板" in ready_output
    assert "仓库根目录：通过" in ready_output
    assert "巨潮连通：通过" in ready_output
    assert str(tmp_path) not in ready_output
    assert "仓库根目录：未通过" in failure_output
    assert "存档读取：未通过" in failure_output
    assert "巨潮连通：未通过" in failure_output
    assert str(tmp_path) not in failure_output


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
