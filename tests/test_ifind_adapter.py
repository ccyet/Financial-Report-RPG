import pytest

from fundamental_pulse.ifind_adapter import (
    IfindConfigurationError,
    IfindHighFrequencyFactorAdapter,
    IfindHttpResponse,
    IfindMcpAdapter,
    IfindMcpClient,
    IfindMcpConfig,
    _highfreq_tool_arguments,
    _quarterly_tool_arguments,
)


class FakeMcpClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return self.response


def test_ifind_adapter_requires_configured_quarterly_tool_name():
    adapter = IfindMcpAdapter(client=FakeMcpClient({}), quarterly_tool_name=None)

    with pytest.raises(IfindConfigurationError, match="quarterly"):
        adapter.fetch_quarterly_records("300750.SZ")


def test_ifind_quarterly_prompt_requests_exact_single_quarter_core_fields():
    arguments = _quarterly_tool_arguments("get_stock_financials", "300750.SZ", "2022Q1", "2024Q4")

    query = arguments["query"]
    assert "单季度.营业收入" in query
    assert "单季度.营业成本" in query
    assert "单季度.销售费用" in query
    assert "单季度.管理费用" in query
    assert "单季度.研发费用" in query
    assert "单季度.财务费用" in query
    assert "单季度.归属于母公司所有者的净利润" in query
    assert "单季度.扣除非经常性损益后的归属母公司股东净利润" in query
    assert "单季度.经营活动产生的现金流量净额" in query


def test_ifind_highfreq_prompt_uses_skills_query_tool_shape():
    arguments = _highfreq_tool_arguments("get_stock_summary", "300750.SZ", 90)

    assert list(arguments) == ["query"]
    assert "300750.SZ" in arguments["query"]
    assert "近 90 天" in arguments["query"]
    assert "结构化 JSON" in arguments["query"]


def test_ifind_highfreq_prompt_accepts_natural_language_query():
    query = "查询宁德时代近90天动力电池装机量、碳酸锂价格和储能中标，按日期返回表格。"

    arguments = _highfreq_tool_arguments(
        "get_stock_summary",
        "300750.SZ",
        90,
        natural_query=query,
    )

    assert arguments == {"query": query}


def test_ifind_adapter_parses_quarterly_records_from_structured_content():
    client = FakeMcpClient(
        {
            "structuredContent": {
                "records": [
                    {
                        "ticker": "300750.SZ",
                        "period": "2025Q4",
                        "revenue": 155,
                        "operating_cost": 100,
                        "net_profit_parent": 18,
                        "net_profit_deducted": 12.5,
                        "operating_cash_flow": 18,
                        "accounts_receivable": 70,
                        "inventory": 39,
                    }
                ]
            }
        }
    )
    adapter = IfindMcpAdapter(client=client, quarterly_tool_name="fetch_quarterly_records")

    records = adapter.fetch_quarterly_records("300750.SZ", start="2025Q1", end="2025Q4")

    assert client.calls == [
        (
            "fetch_quarterly_records",
            {"ticker": "300750.SZ", "start": "2025Q1", "end": "2025Q4"},
        )
    ]
    assert records[0].ticker == "300750.SZ"
    assert records[0].period == "2025Q4"
    assert records[0].revenue == 155
    assert records[0].source == "iFinD MCP"


def test_ifind_adapter_parses_ifind_markdown_answer_with_single_quarter_columns():
    client = FakeMcpClient(
        {
            "content": [
                {
                    "type": "text",
                    "text": (
                        '{"code":1,"msg":"success","data":{"answer":"'
                        "|证券代码|日期|单季度.营业收入（单位：元）|单季度.营业成本（单位：元）|"
                        "单季度.销售费用（单位：元）|单季度.管理费用（单位：元）|"
                        "单季度.研发费用（单位：元）|单季度.财务费用（单位：元）|"
                        "单季度.归属于母公司所有者的净利润（单位：元）|"
                        "单季度.扣除非经常损益后的归属母公司股东净利润（单位：元）|"
                        "应收账款（单位：元）|存货（单位：元）|\\n"
                        "|---|---|---|---|---|---|---|---|---|---|---|---|\\n"
                        "|300750.SZ|20251231|1406.2985亿|1009.5615亿|13.266亿|34.3503亿|"
                        "70.7875亿|-924077000.0|231.6717亿|208.8864亿|764.0326亿|"
                        "945.2624亿|\\n\"}}"
                    ),
                }
            ]
        }
    )
    adapter = IfindMcpAdapter(client=client, quarterly_tool_name="get_stock_financials")

    records = adapter.fetch_quarterly_records("300750.SZ")

    assert records[0].period == "2025Q4"
    assert records[0].revenue == 140629850000.0
    assert records[0].operating_cost == 100956150000.0
    assert records[0].net_profit_parent == 23167170000.0
    assert records[0].net_profit_deducted == 20888640000.0
    assert records[0].non_recurring_gain_loss == 2278530000.0


def test_ifind_high_frequency_adapter_parses_observations():
    client = FakeMcpClient(
        {
            "records": [
                {
                    "ticker": "300750.SZ",
                    "factor_name": "power_battery_installation",
                    "factor_label": "动力电池装机量",
                    "date": "2026-01-31",
                    "value": 122,
                    "frequency": "monthly",
                }
            ]
        }
    )
    adapter = IfindHighFrequencyFactorAdapter(
        client=client,
        high_frequency_tool_name="fetch_high_frequency_factors",
    )

    observations = adapter.fetch_factor_observations(
        "300750.SZ",
        start="2026-01-01",
        end="2026-03-31",
        factor_set="catl",
    )

    assert client.calls == [
        (
            "fetch_high_frequency_factors",
            {
                "ticker": "300750.SZ",
                "start": "2026-01-01",
                "end": "2026-03-31",
                "factor_set": "catl",
            },
        )
    ]
    assert observations[0].factor_name == "power_battery_installation"
    assert observations[0].value == 122
    assert observations[0].source == "ifind_mcp"


def test_ifind_high_frequency_adapter_parses_edb_wide_markdown_answer():
    client = FakeMcpClient(
        {
            "content": [
                {
                    "type": "text",
                    "text": (
                        '{"code":1,"msg":"success","data":{"answer":"'
                        "|日期|新能源汽车:销量:当月值（单位：辆）|\\n"
                        "|---|---|\\n"
                        "|2026-03-31|125.2万|\\n"
                        "|2026-02-28|765000.0|\\n\"}}"
                    ),
                }
            ]
        }
    )
    adapter = IfindHighFrequencyFactorAdapter(
        client=client,
        high_frequency_tool_name="get_edb_data",
    )

    observations = adapter.fetch_factor_observations("300750.SZ", factor_set="catl")

    assert [item.factor_name for item in observations] == [
        "新能源汽车:销量:当月值",
        "新能源汽车:销量:当月值",
    ]
    assert observations[0].date == "2026-03-31"
    assert observations[0].value == 1252000.0


class FakeTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append((url, body, headers, timeout))
        if body["method"] == "initialize":
            return IfindHttpResponse(
                body={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "serverInfo": {"name": "fake-ifind"},
                    },
                },
                headers={"mcp-session-id": "session-1"},
            )
        if body["method"] == "notifications/initialized":
            return IfindHttpResponse(body={}, headers={})
        if body["method"] == "tools/list":
            return IfindHttpResponse(
                body={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "fetch_quarterly_records",
                                "description": "quarterly financial records",
                            }
                        ]
                    },
                },
                headers={},
            )
        raise AssertionError(body["method"])


def test_ifind_client_initializes_session_before_listing_tools():
    transport = FakeTransport()
    client = IfindMcpClient(
        config=IfindMcpConfig(
            url="https://example.test/mcp",
            authorization="Bearer token",
        ),
        transport=transport,
    )

    tools = client.list_tools()

    assert tools == [
        {
            "name": "fetch_quarterly_records",
            "description": "quarterly financial records",
        }
    ]
    assert [call[1]["method"] for call in transport.calls] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]
    assert transport.calls[-1][2]["mcp-session-id"] == "session-1"


def test_ifind_config_loads_mcpservers_file(tmp_path):
    config_path = tmp_path / "ifind.mcp.json"
    config_path.write_text(
        """
{
  "mcpServers": {
    "hexin-ifind-ds-stock-mcp": {
      "headers": {
        "Authorization": "Bearer test-token"
      },
      "type": "streamablehttp",
      "url": "https://api-mcp.example.test/stock"
    }
  },
  "fundamentalPulse": {
    "server": "hexin-ifind-ds-stock-mcp",
    "quarterlyTool": "fetch_quarterly_records",
    "highFrequencyTool": "fetch_high_frequency_factors",
    "timeoutSeconds": 12
  }
}
""",
        encoding="utf-8",
    )

    config = IfindMcpConfig.from_file(config_path)

    assert config.url == "https://api-mcp.example.test/stock"
    assert config.authorization == "Bearer test-token"
    assert config.quarterly_tool_name == "fetch_quarterly_records"
    assert config.high_frequency_tool_name == "fetch_high_frequency_factors"
    assert config.timeout_seconds == 12


def test_ifind_config_can_select_high_frequency_server(tmp_path):
    config_path = tmp_path / "ifind.mcp.json"
    config_path.write_text(
        """
{
  "mcpServers": {
    "hexin-ifind-ds-stock-mcp": {
      "headers": {"Authorization": "Bearer stock-token"},
      "url": "https://api-mcp.example.test/stock"
    },
    "hexin-ifind-ds-edb-mcp": {
      "headers": {"Authorization": "Bearer edb-token"},
      "url": "https://api-mcp.example.test/edb"
    }
  },
  "fundamentalPulse": {
    "server": "hexin-ifind-ds-stock-mcp",
    "highFrequencyServer": "hexin-ifind-ds-edb-mcp",
    "quarterlyTool": "get_stock_financials",
    "highFrequencyTool": "get_edb_data"
  }
}
""",
        encoding="utf-8",
    )

    config = IfindMcpConfig.from_file(
        config_path,
        server_name="hexin-ifind-ds-edb-mcp",
    )

    assert config.url == "https://api-mcp.example.test/edb"
    assert config.authorization == "Bearer edb-token"
    assert config.high_frequency_tool_name == "get_edb_data"


def test_ifind_config_raises_when_server_missing(tmp_path):
    config_path = tmp_path / "ifind.mcp.json"
    config_path.write_text('{"mcpServers": {}}', encoding="utf-8")

    with pytest.raises(IfindConfigurationError, match="mcpServers"):
        IfindMcpConfig.from_file(config_path)
