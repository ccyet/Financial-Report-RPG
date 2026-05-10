from pathlib import Path

from typer.testing import CliRunner

import fundamental_pulse.cli as cli
import fundamental_pulse.workflow as workflow
from fundamental_pulse.cli import _fundamental_pulse_config_value, _quarterly_fetch_bounds, app
from fundamental_pulse.ifind_adapter import IfindMcpConfig, MockIfindMcpAdapter


def test_ifind_tools_reports_missing_config_without_traceback(monkeypatch):
    monkeypatch.delenv("IFIND_MCP_URL", raising=False)
    monkeypatch.delenv("IFIND_STOCK_MCP_URL", raising=False)
    monkeypatch.delenv("IFIND_MCP_AUTHORIZATION", raising=False)
    monkeypatch.delenv("IFIND_STOCK_MCP_AUTHORIZATION", raising=False)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["ifind-tools"])

    assert result.exit_code == 1
    assert "IFIND_MCP_URL" in result.output
    assert "Traceback" not in result.output


def test_fundamental_pulse_config_value_reads_high_frequency_server(tmp_path):
    config_path = tmp_path / "ifind.mcp.json"
    config_path.write_text(
        """
{
  "mcpServers": {},
  "fundamentalPulse": {
    "highFrequencyServer": "hexin-ifind-ds-edb-mcp"
  }
}
""",
        encoding="utf-8",
    )

    value = _fundamental_pulse_config_value(config_path, "highFrequencyServer")

    assert value == "hexin-ifind-ds-edb-mcp"


def test_quarterly_fetch_bounds_include_prior_year_for_yoy():
    assert _quarterly_fetch_bounds("2025Q4") == ("2024Q1", "2025Q4")


def test_ifind_ping_prints_success(monkeypatch):
    class FakeClient:
        def __init__(self, config):
            self.config = config

        def ping(self):
            return True

    monkeypatch.setattr(
        cli.IfindMcpConfig,
        "from_sources",
        classmethod(lambda cls, config_path=None, server_name=None: IfindMcpConfig("url", "token")),
    )
    monkeypatch.setattr(cli, "IfindMcpClient", FakeClient)

    result = CliRunner().invoke(app, ["ifind", "ping"])

    assert result.exit_code == 0
    assert "iFinD MCP 连接正常" in result.output
    assert "token" not in result.output


def test_ifind_pull_quarterly_saves_sanitized_raw_response(monkeypatch):
    class FakeClient:
        def __init__(self, config):
            self.config = config

        def query_quarterly_financials_raw(self, ticker, start_period, end_period):
            return {
                "data": [
                    {
                        "ticker": ticker,
                        "report_period": start_period,
                        "revenue": 1,
                        "source": "iFinD MCP",
                    }
                ],
                "mcp-session-id": "secret-session",
            }

        def query_quarterly_financials(self, ticker, start_period, end_period):
            return self.config.adapter.fetch_quarterly_records(ticker, start_period, end_period)

    class ConfigWithAdapter:
        adapter = MockIfindMcpAdapter()

    monkeypatch.setattr(
        cli.IfindMcpConfig,
        "from_sources",
        classmethod(lambda cls, config_path=None, server_name=None: ConfigWithAdapter()),
    )
    monkeypatch.setattr(cli, "IfindMcpClient", FakeClient)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "ifind",
                "pull-quarterly",
                "300750.SZ",
                "--start",
                "2024Q1",
                "--end",
                "2024Q4",
                "--save-raw",
            ],
        )

        raw_path = "data/raw/ifind_300750_SZ_2024Q1_2024Q4.json"
        assert result.exit_code == 0
        assert "返回记录数" in result.output
        assert "secret-session" not in result.output
        assert "secret-session" not in open(raw_path, encoding="utf-8").read()


def test_analyze_source_ifind_uses_real_source_report_format(monkeypatch):
    class FakeClient:
        def __init__(self, config):
            self.config = config

    class FakeIfindAdapter:
        def __init__(self, client, quarterly_tool_name=None):
            self.client = client

        def fetch_quarterly_records(self, ticker, start=None, end=None):
            assert start == "2024Q1"
            assert end == "2025Q4"
            records = MockIfindMcpAdapter().fetch_quarterly_records(ticker, start=start, end=end)
            return [
                record.model_copy(update={"source": "iFinD MCP", "unit": "CNY"})
                for record in records
            ]

    monkeypatch.setattr(
        workflow.IfindMcpConfig,
        "from_sources",
        classmethod(lambda cls, config_path=None, server_name=None: IfindMcpConfig("url", "token")),
    )
    monkeypatch.setattr(workflow, "IfindMcpClient", FakeClient)
    monkeypatch.setattr(workflow, "IfindMcpAdapter", FakeIfindAdapter)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "analyze",
                "300750.SZ",
                "--source",
                "ifind",
                "--start",
                "2024Q1",
                "--end",
                "2025Q4",
            ],
        )

        assert result.exit_code == 0
        report = open("reports/300750.SZ_2025Q4.md", encoding="utf-8").read()
        assert "- 数据源：iFinD MCP" in report
        assert "- 报告期：2024Q1 至 2025Q4" in report


def test_analyze_mock_with_highfreq_adds_report_section():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "analyze",
                "300750.SZ",
                "--mock",
                "--with-highfreq",
                "--lookback-days",
                "90",
            ],
        )

        assert result.exit_code == 0
        report = open("reports/300750.SZ_2025Q4.md", encoding="utf-8").read()
        assert "高频经营信号验证" in report
        assert "海外储能订单增加" in report


def test_analyze_mock_records_run_history():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "300750.SZ", "--mock"])

        assert result.exit_code == 0
        assert Path("reports/index.json").exists()
        assert "报告路径：reports/300750.SZ_2025Q4.md" in result.output


def test_thesis_verify_cli_mock_runs(tmp_path):
    thesis_path = tmp_path / "300750.yml"
    thesis_path.write_text(
        """
ticker: 300750.SZ
name: 宁德时代季度经营假设
drivers:
  - id: revenue_growth
    name: 收入增速
    metric: revenue_yoy
    operator: ">="
    threshold: 0.1
  - id: highfreq_revenue
    name: 高频收入端验证
    highfreq_side: revenue_side
    expected: positive
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "thesis",
            "verify",
            "300750.SZ",
            "--thesis-file",
            str(thesis_path),
            "--mock",
        ],
    )

    assert result.exit_code == 0
    assert "投资假设验证：unknown" in result.output
    assert "收入增速" in result.output
    assert "买入" not in result.output
    assert "卖出" not in result.output
    assert "目标价" not in result.output


def test_thesis_verify_cli_rejects_ticker_mismatch(tmp_path):
    thesis_path = tmp_path / "mismatch.json"
    thesis_path.write_text(
        '{"ticker":"600000.SH","name":"错配假设","drivers":[]}',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "thesis",
            "verify",
            "300750.SZ",
            "--thesis-file",
            str(thesis_path),
            "--mock",
        ],
    )

    assert result.exit_code == 1
    assert "ticker" in result.output
    assert "Traceback" not in result.output


def test_analyze_with_thesis_file_adds_report_section(tmp_path):
    thesis_path = tmp_path / "300750.yml"
    thesis_path.write_text(
        """
ticker: 300750.SZ
name: 宁德时代季度经营假设
drivers:
  - id: revenue_growth
    name: 收入增速
    metric: revenue_yoy
    operator: ">="
    threshold: 0.1
  - id: highfreq_revenue
    name: 高频收入端验证
    highfreq_side: revenue_side
    expected: positive
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "analyze",
                "300750.SZ",
                "--mock",
                "--with-highfreq",
                "--thesis-file",
                str(thesis_path),
            ],
        )

        assert result.exit_code == 0
        report = open("reports/300750.SZ_2025Q4.md", encoding="utf-8").read()
        assert "## 投资假设验证" in report
        assert "汇总状态" in report
        assert "不构成投资建议" in report
        assert "买入" not in report
        assert "卖出" not in report
        assert "目标价" not in report


def test_ifind_pull_highfreq_accepts_empty_ifind_datas(monkeypatch):
    class FakeClient:
        def __init__(self, config):
            self.config = config
            self.tool_name = None

        def resolve_high_freq_tool_name(self, tool_name=None):
            return tool_name or "get_stock_summary"

        def query_high_freq_signals_raw(
            self,
            ticker,
            lookback_days=90,
            tool_name=None,
            natural_query=None,
        ):
            self.tool_name = tool_name
            self.natural_query = natural_query
            return {
                "content": [
                    {
                        "type": "text",
                        "text": '{"code":1,"msg":"success","data":{"answer":"","datas":[]}}',
                    }
                ],
                "mcp-session-id": "secret-session",
            }

    monkeypatch.setattr(
        cli.IfindMcpConfig,
        "from_sources",
        classmethod(lambda cls, config_path=None, server_name=None: IfindMcpConfig("url", "token")),
    )
    monkeypatch.setattr(cli, "IfindMcpClient", FakeClient)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "ifind",
                "pull-highfreq",
                "300750.SZ",
                "--lookback-days",
                "90",
                "--ifind-high-frequency-tool",
                "get_stock_summary",
                "--query",
                "查询宁德时代近90天动力电池装机量，按日期返回表格。",
                "--save-raw",
            ],
        )

        assert result.exit_code == 0
        assert "返回高频信号数：0" in result.output
        assert "高频工具：get_stock_summary" in result.output
        raw_path = next(iter(Path("data/raw").glob("ifind_highfreq_*.json")))
        raw_text = raw_path.read_text(encoding="utf-8")
        assert "get_stock_summary" in raw_text
        assert "查询宁德时代近90天动力电池装机量" in raw_text
        assert "secret-session" not in raw_text
