from pathlib import Path

from typer.testing import CliRunner

from fundamental_pulse.cli import app
from fundamental_pulse.watchlist import load_watchlist, run_watchlist


def test_load_watchlist_yaml_example():
    watchlist = load_watchlist("examples/watchlists/core_a_share.yml")

    assert watchlist.name == "核心 A 股观察列表"
    assert len(watchlist.items) >= 2
    assert watchlist.items[0].ticker == "300750.SZ"
    assert watchlist.items[0].thesis_file == Path("examples/thesis/300750.yml")


def test_run_watchlist_limit_one_writes_reports_and_index(tmp_path):
    watchlist = load_watchlist("examples/watchlists/core_a_share.yml")

    result = run_watchlist(
        watchlist,
        mock=True,
        limit=1,
        reports_dir=tmp_path,
    )

    assert result.name == "核心 A 股观察列表"
    assert result.total == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.items[0].ticker == "300750.SZ"
    assert result.items[0].status == "success"
    assert Path(result.items[0].report_path).exists()
    assert (tmp_path / "index.json").exists()


def test_run_watchlist_continues_after_item_error(tmp_path):
    watchlist_path = tmp_path / "bad.yml"
    watchlist_path.write_text(
        """
name: 错误恢复观察列表
items:
  - ticker: 600000.SH
    name: 错配 thesis
    thesis_file: examples/thesis/300750.yml
  - ticker: 300750.SZ
    name: 宁德时代
""",
        encoding="utf-8",
    )
    watchlist = load_watchlist(watchlist_path)

    result = run_watchlist(watchlist, mock=True, reports_dir=tmp_path)

    assert result.total == 2
    assert result.failed == 1
    assert result.succeeded == 1
    assert result.items[0].status == "failed"
    assert "ticker" in result.items[0].error_summary
    assert result.items[1].status == "success"


def test_watchlist_cli_runs_limit_one():
    watchlist_path = Path(__file__).parents[1] / "examples/watchlists/core_a_share.yml"
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "watchlist",
                "run",
                str(watchlist_path),
                "--mock",
                "--limit",
                "1",
            ],
        )

        assert result.exit_code == 0
        assert "观察列表：核心 A 股观察列表" in result.output
        assert "成功：1" in result.output
        assert "失败：0" in result.output
        assert "买入" not in result.output
        assert "卖出" not in result.output
        assert "目标价" not in result.output
