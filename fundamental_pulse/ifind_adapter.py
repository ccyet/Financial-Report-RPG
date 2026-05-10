from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fundamental_pulse.models import HighFrequencyObservation, QuarterRecord

_MISSING = object()
QUERY_STYLE_TOOLS = {"get_stock_financials", "get_edb_data", "search_edb"}
DEFAULT_IFIND_CONFIG_PATH = Path("ifind.mcp.json")
IFIND_SOURCE_LABEL = "iFinD MCP"
FIELD_ALIASES = {
    "ticker": "ticker",
    "symbol": "ticker",
    "stock_code": "ticker",
    "证券代码": "ticker",
    "报告期": "report_period",
    "report_period": "report_period",
    "period": "report_period",
    "quarter": "report_period",
    "日期": "report_period",
    "披露日期": "disclosure_date",
    "disclosure_date": "disclosure_date",
    "是否累计口径": "is_cumulative",
    "is_cumulative": "is_cumulative",
    "营业收入": "revenue",
    "营业总收入": "revenue",
    "revenue": "revenue",
    "营业成本": "operating_cost",
    "operating_cost": "operating_cost",
    "销售费用": "selling_expense",
    "selling_expense": "selling_expense",
    "管理费用": "admin_expense",
    "admin_expense": "admin_expense",
    "研发费用": "rd_expense",
    "rd_expense": "rd_expense",
    "财务费用": "financial_expense",
    "financial_expense": "financial_expense",
    "营业利润": "operating_profit",
    "operating_profit": "operating_profit",
    "归母净利润": "net_profit_parent",
    "归属于母公司所有者的净利润": "net_profit_parent",
    "net_profit_parent": "net_profit_parent",
    "扣非归母净利润": "net_profit_deducted",
    "扣除非经常性损益后的净利润": "net_profit_deducted",
    "扣除非经常性损益后的归属母公司股东净利润": "net_profit_deducted",
    "扣除非经常损益后的归属母公司股东净利润": "net_profit_deducted",
    "net_profit_deducted": "net_profit_deducted",
    "投资收益": "investment_income",
    "investment_income": "investment_income",
    "公允价值变动": "fair_value_change",
    "公允价值变动收益": "fair_value_change",
    "fair_value_change": "fair_value_change",
    "资产减值损失": "asset_impairment_loss",
    "asset_impairment_loss": "asset_impairment_loss",
    "信用减值损失": "credit_impairment_loss",
    "credit_impairment_loss": "credit_impairment_loss",
    "非经常性损益": "non_recurring_gain_loss",
    "non_recurring_gain_loss": "non_recurring_gain_loss",
    "经营活动现金流净额": "operating_cash_flow",
    "经营活动产生的现金流量净额": "operating_cash_flow",
    "经营现金流": "operating_cash_flow",
    "operating_cash_flow": "operating_cash_flow",
    "资本开支": "capex",
    "购建固定资产、无形资产和其他长期资产支付的现金": "capex",
    "capex": "capex",
    "应收账款": "accounts_receivable",
    "accounts_receivable": "accounts_receivable",
    "存货": "inventory",
    "inventory": "inventory",
    "合同负债": "contract_liability",
    "contract_liability": "contract_liability",
    "总资产": "total_assets",
    "资产总计": "total_assets",
    "total_assets": "total_assets",
    "总负债": "total_liabilities",
    "负债合计": "total_liabilities",
    "total_liabilities": "total_liabilities",
    "单位": "unit",
    "unit": "unit",
    "数据来源": "source",
    "source": "source",
}
NUMERIC_QUARTER_FIELDS = {
    "revenue",
    "operating_cost",
    "selling_expense",
    "admin_expense",
    "rd_expense",
    "financial_expense",
    "operating_profit",
    "net_profit_parent",
    "net_profit_deducted",
    "investment_income",
    "fair_value_change",
    "asset_impairment_loss",
    "credit_impairment_loss",
    "non_recurring_gain_loss",
    "operating_cash_flow",
    "capex",
    "accounts_receivable",
    "inventory",
    "contract_liability",
    "total_assets",
    "total_liabilities",
}
REQUIRED_FINANCIAL_FIELDS = ("revenue", "net_profit_parent", "net_profit_deducted")
UNIT_MULTIPLIERS = {
    "元": 1.0,
    "CNY": 1.0,
    "RMB": 1.0,
    "万元": 10_000.0,
    "亿元": 100_000_000.0,
}
HIGH_FREQUENCY_METADATA_FIELDS = {
    "ticker",
    "symbol",
    "stock_code",
    "证券代码",
    "证券简称",
    "date",
    "trade_date",
    "report_date",
    "日期",
    "frequency",
}


class IfindMcpError(RuntimeError):
    pass


class IfindConfigurationError(IfindMcpError):
    pass


class IfindMcpResponseError(IfindMcpError):
    pass


@dataclass(frozen=True)
class IfindMcpConfig:
    url: str | None
    authorization: str | None
    quarterly_tool_name: str | None = None
    high_frequency_tool_name: str | None = None
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> IfindMcpConfig:
        return cls(
            url=os.getenv("IFIND_MCP_URL") or os.getenv("IFIND_STOCK_MCP_URL"),
            authorization=os.getenv("IFIND_MCP_AUTHORIZATION")
            or os.getenv("IFIND_MCP_API_KEY")
            or os.getenv("IFIND_STOCK_MCP_AUTHORIZATION"),
            quarterly_tool_name=os.getenv("IFIND_MCP_FINANCIAL_TOOL")
            or os.getenv("IFIND_MCP_QUARTERLY_TOOL")
            or os.getenv("IFIND_STOCK_MCP_QUARTERLY_TOOL"),
            high_frequency_tool_name=os.getenv("IFIND_MCP_HIGH_FREQUENCY_TOOL")
            or os.getenv("IFIND_STOCK_MCP_HIGH_FREQUENCY_TOOL"),
            timeout_seconds=float(os.getenv("IFIND_MCP_TIMEOUT_SECONDS", "30")),
        )

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        server_name: str | None = None,
    ) -> IfindMcpConfig:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise IfindConfigurationError("iFinD config file must contain a JSON object.")

        pulse_config = payload.get("fundamentalPulse", {})
        if pulse_config is None:
            pulse_config = {}
        if not isinstance(pulse_config, dict):
            raise IfindConfigurationError("fundamentalPulse config must be an object.")

        mcp_servers = payload.get("mcpServers")
        if not isinstance(mcp_servers, dict) or not mcp_servers:
            raise IfindConfigurationError("config file must contain non-empty mcpServers.")

        selected_server = (
            server_name
            or _string_or_none(pulse_config.get("server"))
            or os.getenv("IFIND_MCP_SERVER")
            or os.getenv("IFIND_MCP_SERVER_NAME")
            or next(iter(mcp_servers))
        )
        server_config = mcp_servers.get(selected_server)
        if not isinstance(server_config, dict):
            raise IfindConfigurationError(
                f"mcpServers does not contain selected server: {selected_server}"
            )

        headers = server_config.get("headers", {})
        if headers is None:
            headers = {}
        if not isinstance(headers, dict):
            raise IfindConfigurationError("selected MCP server headers must be an object.")

        return cls(
            url=_string_or_none(server_config.get("url")),
            authorization=_string_or_none(headers.get("Authorization")),
            quarterly_tool_name=_string_or_none(
                pulse_config.get("financialTool")
                or pulse_config.get("financial_tool_name")
                or pulse_config.get("financial_tool")
                or pulse_config.get("quarterlyTool")
                or pulse_config.get("quarterly_tool_name")
                or pulse_config.get("quarterly_tool")
            ),
            high_frequency_tool_name=_string_or_none(
                pulse_config.get("highFrequencyTool")
                or pulse_config.get("high_frequency_tool_name")
                or pulse_config.get("high_frequency_tool")
            ),
            timeout_seconds=float(pulse_config.get("timeoutSeconds", 30.0)),
        )

    @classmethod
    def from_sources(
        cls,
        config_path: str | Path | None = None,
        server_name: str | None = None,
    ) -> IfindMcpConfig:
        resolved_path = config_path or os.getenv("IFIND_MCP_CONFIG")
        if not resolved_path and DEFAULT_IFIND_CONFIG_PATH.exists():
            resolved_path = DEFAULT_IFIND_CONFIG_PATH
        if resolved_path:
            return cls.from_file(resolved_path, server_name=server_name)
        return cls.from_env()


@dataclass(frozen=True)
class IfindHttpResponse:
    body: Any
    headers: dict[str, str]


class IfindMcpClient:
    def __init__(self, config: IfindMcpConfig | None = None, transport: Any | None = None):
        self.config = config or IfindMcpConfig.from_env()
        self._request_id = 0
        self._transport = transport or _urllib_transport
        self._session_id: str | None = None
        self._initialized = False

    def initialize(self) -> dict[str, Any]:
        result = self._send_jsonrpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "fundamental-pulse", "version": "0.1.0"},
            },
            requires_session=False,
        )
        self._send_jsonrpc("notifications/initialized", None, notification=True)
        self._initialized = True
        return result if isinstance(result, dict) else {}

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        result = self._send_jsonrpc("tools/list", {})
        if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
            raise IfindMcpResponseError("iFinD MCP tools/list response missing tools.")
        return [_ensure_mapping(tool) for tool in result["tools"]]

    def ping(self) -> bool:
        self.list_tools()
        return True

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self._ensure_initialized()
        return self._send_jsonrpc(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )

    def query_quarterly_financials(
        self,
        ticker: str,
        start_period: str,
        end_period: str,
    ) -> list[QuarterRecord]:
        raw = self.query_quarterly_financials_raw(ticker, start_period, end_period)
        return parse_ifind_quarterly_response(raw, ticker=ticker)

    def query_quarterly_financials_raw(
        self,
        ticker: str,
        start_period: str,
        end_period: str,
    ) -> Any:
        tool_name = self._resolve_financial_tool_name()
        return self.call_tool(
            tool_name,
            _quarterly_tool_arguments(tool_name, ticker, start_period, end_period),
        )

    def query_high_freq_signals(
        self,
        ticker: str,
        lookback_days: int = 90,
        tool_name: str | None = None,
        natural_query: str | None = None,
    ) -> list[Any]:
        from fundamental_pulse.highfreq import parse_highfreq_response

        raw = self.query_high_freq_signals_raw(
            ticker,
            lookback_days=lookback_days,
            tool_name=tool_name,
            natural_query=natural_query,
        )
        return parse_highfreq_response(raw, ticker=ticker)

    def query_high_freq_signals_raw(
        self,
        ticker: str,
        lookback_days: int = 90,
        tool_name: str | None = None,
        natural_query: str | None = None,
    ) -> Any:
        resolved_tool_name = self.resolve_high_freq_tool_name(tool_name=tool_name)
        return self.call_tool(
            resolved_tool_name,
            _highfreq_tool_arguments(
                resolved_tool_name,
                ticker,
                lookback_days,
                natural_query=natural_query,
            ),
        )

    def resolve_high_freq_tool_name(self, tool_name: str | None = None) -> str:
        return tool_name or self._resolve_high_freq_tool_name()

    def _resolve_financial_tool_name(self) -> str:
        if self.config.quarterly_tool_name:
            return self.config.quarterly_tool_name

        tools = self.list_tools()
        for tool in tools:
            name = str(tool.get("name", ""))
            description = str(tool.get("description", ""))
            searchable = f"{name} {description}".lower()
            if "financial" in searchable or "财务" in searchable:
                return name

        raise IfindConfigurationError(
            "Unable to discover iFinD MCP tools. Set IFIND_MCP_FINANCIAL_TOOL explicitly."
        )

    def _resolve_high_freq_tool_name(self) -> str:
        if self.config.high_frequency_tool_name:
            return self.config.high_frequency_tool_name

        tools = self.list_tools()
        preferred_keywords = ("news", "event", "summary", "edb", "新闻", "事件", "摘要")
        for tool in tools:
            name = str(tool.get("name", ""))
            description = str(tool.get("description", ""))
            searchable = f"{name} {description}".lower()
            if any(keyword.lower() in searchable for keyword in preferred_keywords):
                return name

        raise IfindConfigurationError(
            "Unable to discover iFinD MCP high-frequency tool. "
            "Set IFIND_MCP_HIGH_FREQUENCY_TOOL explicitly."
        )

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def _send_jsonrpc(
        self,
        method: str,
        params: dict[str, Any] | None,
        requires_session: bool = True,
        notification: bool = False,
    ) -> Any:
        if not self.config.url:
            raise IfindConfigurationError("IFIND_MCP_URL is required for real iFinD MCP calls.")
        if not self.config.authorization:
            raise IfindConfigurationError(
                "IFIND_MCP_API_KEY or IFIND_MCP_AUTHORIZATION is required for real iFinD MCP calls."
            )

        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "tools/call",
        }
        if not notification:
            self._request_id += 1
            body["id"] = self._request_id
        body["method"] = method
        if params is not None:
            body["params"] = params

        headers = {
            "Authorization": self.config.authorization,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        }
        if requires_session and self._session_id:
            headers["mcp-session-id"] = self._session_id

        response = self._transport(self.config.url, body, headers, self.config.timeout_seconds)
        session_id = _case_insensitive_get(response.headers, "mcp-session-id")
        if session_id:
            self._session_id = session_id
        if notification:
            return None
        if isinstance(response.body, dict) and "error" in response.body:
            raise IfindMcpResponseError(f"iFinD MCP returned error: {response.body['error']}")
        if isinstance(response.body, dict) and "result" in response.body:
            return response.body["result"]
        return response.body


class IfindMcpAdapter:
    """Adapter for quarterly financial records from iFinD MCP."""

    def __init__(
        self,
        client: IfindMcpClient | None = None,
        quarterly_tool_name: str | None = None,
    ):
        self.client = client or IfindMcpClient()
        config_tool = getattr(getattr(self.client, "config", None), "quarterly_tool_name", None)
        self.quarterly_tool_name = quarterly_tool_name or config_tool

    def fetch_quarterly_records(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[QuarterRecord]:
        if not self.quarterly_tool_name:
            raise IfindConfigurationError(
                "quarterly MCP tool name is required. Set IFIND_MCP_QUARTERLY_TOOL "
                "or pass --ifind-quarterly-tool."
            )

        payload = self.client.call_tool(
            self.quarterly_tool_name,
            _quarterly_tool_arguments(self.quarterly_tool_name, ticker, start, end),
        )
        return parse_ifind_quarterly_response(payload, ticker=ticker)


class IfindHighFrequencyFactorAdapter:
    """Adapter for high-frequency factor observations from iFinD MCP."""

    def __init__(
        self,
        client: IfindMcpClient | None = None,
        high_frequency_tool_name: str | None = None,
    ):
        self.client = client or IfindMcpClient()
        config_tool = getattr(
            getattr(self.client, "config", None),
            "high_frequency_tool_name",
            None,
        )
        self.high_frequency_tool_name = high_frequency_tool_name or config_tool

    def fetch_factor_observations(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
        factor_set: str | None = None,
    ) -> list[HighFrequencyObservation]:
        if not self.high_frequency_tool_name:
            raise IfindConfigurationError(
                "high-frequency MCP tool name is required. Set IFIND_MCP_HIGH_FREQUENCY_TOOL "
                "or pass --ifind-high-frequency-tool."
            )

        payload = self.client.call_tool(
            self.high_frequency_tool_name,
            _high_frequency_tool_arguments(
                self.high_frequency_tool_name,
                ticker,
                start,
                end,
                factor_set,
            ),
        )
        records = _extract_records(payload)
        observations: list[HighFrequencyObservation] = []
        for record in records:
            observations.extend(
                _high_frequency_observations_from_mapping(record, fallback_ticker=ticker)
            )
        return observations


class MockIfindMcpAdapter:
    def fetch_quarterly_records(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[QuarterRecord]:
        records = [
            QuarterRecord(
                ticker=ticker,
                period="2024Q1",
                revenue=100,
                operating_cost=65,
                selling_expense=8,
                admin_expense=5,
                rd_expense=6,
                financial_expense=1,
                net_profit_parent=9,
                net_profit_deducted=8,
                non_recurring_gain_loss=1,
                operating_cash_flow=10,
                accounts_receivable=40,
                inventory=30,
            ),
            QuarterRecord(
                ticker=ticker,
                period="2024Q2",
                revenue=120,
                operating_cost=78,
                selling_expense=9,
                admin_expense=6,
                rd_expense=6,
                financial_expense=1,
                net_profit_parent=10,
                net_profit_deducted=9,
                non_recurring_gain_loss=1,
                operating_cash_flow=12,
                accounts_receivable=45,
                inventory=32,
            ),
            QuarterRecord(
                ticker=ticker,
                period="2024Q3",
                revenue=130,
                operating_cost=84.5,
                selling_expense=10,
                admin_expense=6,
                rd_expense=7,
                financial_expense=1,
                net_profit_parent=11,
                net_profit_deducted=10,
                non_recurring_gain_loss=1,
                operating_cash_flow=12,
                accounts_receivable=50,
                inventory=34,
            ),
            QuarterRecord(
                ticker=ticker,
                period="2024Q4",
                revenue=140,
                operating_cost=91,
                selling_expense=11,
                admin_expense=7,
                rd_expense=7,
                financial_expense=1,
                net_profit_parent=12,
                net_profit_deducted=11,
                non_recurring_gain_loss=1,
                operating_cash_flow=14,
                accounts_receivable=55,
                inventory=36,
            ),
            QuarterRecord(
                ticker=ticker,
                period="2025Q1",
                revenue=125,
                operating_cost=80,
                selling_expense=9,
                admin_expense=6,
                rd_expense=7,
                financial_expense=1,
                net_profit_parent=10.5,
                net_profit_deducted=10,
                non_recurring_gain_loss=0.5,
                operating_cash_flow=12,
                accounts_receivable=47,
                inventory=33,
            ),
            QuarterRecord(
                ticker=ticker,
                period="2025Q2",
                revenue=130,
                operating_cost=75,
                selling_expense=9,
                admin_expense=6,
                rd_expense=7,
                financial_expense=1,
                net_profit_parent=12.5,
                net_profit_deducted=12,
                non_recurring_gain_loss=0.5,
                operating_cash_flow=14,
                accounts_receivable=52,
                inventory=35,
            ),
            QuarterRecord(
                ticker=ticker,
                period="2025Q3",
                revenue=150,
                operating_cost=95,
                selling_expense=11,
                admin_expense=7,
                rd_expense=8,
                financial_expense=1,
                net_profit_parent=14,
                net_profit_deducted=13,
                non_recurring_gain_loss=1,
                operating_cash_flow=4,
                accounts_receivable=60,
                inventory=38,
            ),
            QuarterRecord(
                ticker=ticker,
                period="2025Q4",
                revenue=155,
                operating_cost=100,
                selling_expense=12,
                admin_expense=7,
                rd_expense=8,
                financial_expense=1,
                net_profit_parent=18,
                net_profit_deducted=12.5,
                non_recurring_gain_loss=6,
                operating_cash_flow=18,
                accounts_receivable=70,
                inventory=39,
            ),
        ]
        return [
            record.model_copy(update={"unit": "万元"})
            for record in records
            if (start is None or record.period >= start) and (end is None or record.period <= end)
        ]


def parse_ifind_quarterly_response(
    raw: dict[str, Any] | list[Any] | str,
    ticker: str,
) -> list[QuarterRecord]:
    try:
        records = _extract_records(json.loads(raw) if isinstance(raw, str) else raw)
    except (json.JSONDecodeError, IfindMcpResponseError) as exc:
        raise IfindMcpResponseError("Unable to parse iFinD quarterly response.") from exc

    parsed_records = [
        _quarter_record_from_mapping(record, fallback_ticker=ticker) for record in records
    ]
    return _validate_and_dedupe_quarter_records(parsed_records, ticker=ticker)


def normalize_report_period(value: Any) -> str:
    text = str(value).strip()
    if len(text) == 6 and text[4] == "Q" and text[:4].isdigit() and text[5] in "1234":
        return text

    normalized_text = text.replace("/", "-")
    compact = normalized_text.replace("-", "")
    if len(compact) >= 8 and compact[:8].isdigit():
        year = compact[:4]
        month_day = compact[4:8]
        quarter_by_month_day = {"0331": "1", "0630": "2", "0930": "3", "1231": "4"}
        quarter = quarter_by_month_day.get(month_day)
        if quarter is None:
            month = int(compact[4:6])
            quarter = str((month - 1) // 3 + 1)
        return f"{year}Q{quarter}"

    match = re.match(r"^(?P<year>\d{4})年(?P<label>一季报|中报|半年报|三季报|年报|报)$", text)
    if match:
        label_to_quarter = {
            "一季报": "1",
            "中报": "2",
            "半年报": "2",
            "三季报": "3",
            "年报": "4",
            "报": "4",
        }
        return f"{match.group('year')}Q{label_to_quarter[match.group('label')]}"

    raise IfindMcpResponseError(f"Invalid report period: {value}")


def _decode_mcp_response(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("data:"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in stripped.splitlines()
            if line.startswith("data:")
        ]
        stripped = data_lines[-1] if data_lines else stripped

    payload = json.loads(stripped)
    if "error" in payload:
        raise IfindMcpResponseError(f"iFinD MCP returned error: {payload['error']}")
    return payload.get("result", payload)


def _urllib_transport(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: float,
) -> IfindHttpResponse:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            decoded_body = _decode_mcp_response(response.read().decode("utf-8"))
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return IfindHttpResponse(body=decoded_body, headers=response_headers)
    except urllib.error.URLError as exc:
        raise IfindMcpResponseError(f"iFinD MCP request failed: {exc}") from exc


def _case_insensitive_get(headers: dict[str, str], key: str) -> str | None:
    target = key.lower()
    for header_key, value in headers.items():
        if header_key.lower() == target:
            return value
    return None


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_ensure_mapping(item) for item in payload]
    if not isinstance(payload, dict):
        raise IfindMcpResponseError("iFinD MCP payload must be a list or object.")

    candidates = [
        payload.get("records"),
        payload.get("data"),
        payload.get("result"),
        payload.get("rows"),
        payload.get("items"),
        _nested_get(payload, ["structuredContent", "records"]),
        _nested_get(payload, ["structured_content", "records"]),
        _nested_get(payload, ["result", "records"]),
        _nested_get(payload, ["result", "rows"]),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [_ensure_mapping(item) for item in candidate]

    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parsed = json.loads(item["text"])
                return _extract_records(parsed)

    answer = _nested_get(payload, ["data", "answer"])
    if isinstance(answer, str):
        return _parse_markdown_table(answer)

    raise IfindMcpResponseError("Unable to find records in iFinD MCP payload.")


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IfindMcpResponseError("Record item must be an object.")
    return value


def _nested_get(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _quarter_record_from_mapping(
    record: dict[str, Any],
    fallback_ticker: str,
) -> QuarterRecord:
    normalized = _normalize_quarter_mapping(record)
    unit, unit_multiplier = _normalize_unit(normalized.get("unit"))
    values = {
        key: _normalize_numeric_value(value, unit_multiplier)
        for key, value in normalized.items()
        if key in NUMERIC_QUARTER_FIELDS
    }

    net_profit_parent = values.get("net_profit_parent")
    net_profit_deducted = values.get("net_profit_deducted")
    non_recurring_gain_loss = values.get("non_recurring_gain_loss")
    if (
        non_recurring_gain_loss is None
        and net_profit_parent is not None
        and net_profit_deducted is not None
    ):
        non_recurring_gain_loss = net_profit_parent - net_profit_deducted

    return QuarterRecord(
        ticker=str(normalized.get("ticker") or fallback_ticker),
        period=normalize_report_period(
            _pick(normalized, "report_period", default=normalized.get("period"))
        ),
        disclosure_date=_string_or_none(normalized.get("disclosure_date")),
        is_cumulative=_bool_from_value(normalized.get("is_cumulative")),
        unit=unit,
        revenue=values.get("revenue"),
        operating_cost=values.get("operating_cost"),
        selling_expense=values.get("selling_expense"),
        admin_expense=values.get("admin_expense"),
        rd_expense=values.get("rd_expense"),
        financial_expense=values.get("financial_expense"),
        operating_profit=values.get("operating_profit"),
        net_profit_parent=net_profit_parent,
        net_profit_deducted=net_profit_deducted,
        investment_income=values.get("investment_income"),
        fair_value_change=values.get("fair_value_change"),
        asset_impairment_loss=values.get("asset_impairment_loss"),
        credit_impairment_loss=values.get("credit_impairment_loss"),
        non_recurring_gain_loss=non_recurring_gain_loss,
        operating_cash_flow=values.get("operating_cash_flow"),
        capex=values.get("capex"),
        accounts_receivable=values.get("accounts_receivable"),
        inventory=values.get("inventory"),
        contract_liability=values.get("contract_liability"),
        total_assets=values.get("total_assets"),
        total_liabilities=values.get("total_liabilities"),
        source=str(normalized.get("source") or IFIND_SOURCE_LABEL),
    )


def _normalize_quarter_mapping(record: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for raw_key, value in record.items():
        canonical_key = _canonical_quarter_key(raw_key)
        if canonical_key is not None:
            normalized[canonical_key] = value
    return normalized


def _canonical_quarter_key(raw_key: str) -> str | None:
    key = _clean_column_name(str(raw_key))
    for prefix in ("单季度.", "单季度．"):
        if key.startswith(prefix):
            key = key.removeprefix(prefix)
    return FIELD_ALIASES.get(key)


def _normalize_unit(raw_unit: Any) -> tuple[str, float]:
    if raw_unit in (None, ""):
        return "CNY", 1.0
    unit = str(raw_unit).strip()
    multiplier = UNIT_MULTIPLIERS.get(unit)
    if multiplier is not None:
        return "CNY", multiplier
    return unit, 1.0


def _normalize_numeric_value(value: Any, unit_multiplier: float) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, int | float):
        return float(value) * unit_multiplier

    text = str(value).strip()
    if _has_inline_unit(text):
        return _float_or_none(text)
    number = _float_or_none(text)
    if number is None:
        return None
    return number * unit_multiplier


def _has_inline_unit(text: str) -> bool:
    normalized = text.strip().upper()
    return normalized.endswith(("亿元", "万元", "亿", "万", "元", "CNY", "RMB", "%"))


def _bool_from_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, int | float):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "累计", "累计口径"}


def _validate_and_dedupe_quarter_records(
    records: list[QuarterRecord],
    ticker: str,
) -> list[QuarterRecord]:
    if not records:
        return []

    deduped: dict[tuple[str, str], QuarterRecord] = {}
    for record in records:
        if not record.ticker:
            raise IfindMcpResponseError("Parsed iFinD data contains a record without ticker.")
        if not record.period:
            raise IfindMcpResponseError(
                "Parsed iFinD data contains a record without report_period."
            )
        if all(getattr(record, field) is None for field in REQUIRED_FINANCIAL_FIELDS):
            raise IfindMcpResponseError(
                "Parsed iFinD data contains no revenue or profit fields for "
                f"{ticker} {record.period}."
            )

        key = (record.ticker, record.period)
        existing = deduped.get(key)
        if existing is None or _financial_field_score(record) >= _financial_field_score(existing):
            deduped[key] = record

    return sorted(
        deduped.values(),
        key=lambda record: (record.ticker, _period_sort_key(record.period)),
    )


def _financial_field_score(record: QuarterRecord) -> int:
    return sum(getattr(record, field) is not None for field in NUMERIC_QUARTER_FIELDS)


def _period_sort_key(period: str) -> tuple[int, int]:
    return int(period[:4]), int(period[5])


def _high_frequency_observation_from_mapping(
    record: dict[str, Any],
    fallback_ticker: str,
) -> HighFrequencyObservation:
    return HighFrequencyObservation(
        ticker=str(_pick(record, "ticker", "symbol", "stock_code", default=fallback_ticker)),
        factor_name=str(_pick(record, "factor_name", "name")),
        factor_label=str(_pick(record, "factor_label", "label", "factor_name", "name")),
        date=str(_pick(record, "date", "trade_date", "report_date", "日期")),
        value=_float_or_none(_pick(record, "value", "factor_value", "数值")) or 0.0,
        frequency=str(_pick(record, "frequency", default="monthly")),
        source="ifind_mcp",
    )


def _high_frequency_observations_from_mapping(
    record: dict[str, Any],
    fallback_ticker: str,
) -> list[HighFrequencyObservation]:
    if "factor_name" in record or "name" in record:
        return [_high_frequency_observation_from_mapping(record, fallback_ticker=fallback_ticker)]

    ticker = str(
        _pick(record, "ticker", "symbol", "stock_code", "证券代码", default=fallback_ticker)
    )
    observation_date = str(_pick(record, "date", "trade_date", "report_date", "日期"))
    observations: list[HighFrequencyObservation] = []
    for column, raw_value in record.items():
        factor_label = _clean_column_name(column)
        if factor_label in HIGH_FREQUENCY_METADATA_FIELDS:
            continue
        value = _try_float(raw_value)
        if value is None:
            continue
        observations.append(
            HighFrequencyObservation(
                ticker=ticker,
                factor_name=factor_label,
                factor_label=factor_label,
                date=observation_date,
                value=value,
                frequency=str(_pick(record, "frequency", default="monthly")),
                source="ifind_mcp",
            )
        )

    if not observations:
        raise IfindMcpResponseError("Unable to find high-frequency factor values in record.")
    return observations


def _pick(record: dict[str, Any], *keys: str, default: Any = _MISSING) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    if default is not _MISSING:
        return default
    raise IfindMcpResponseError(f"Missing required field. Tried: {', '.join(keys)}")


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, int | float):
        return float(value)

    text = str(value).strip().replace(",", "").replace("\t", "").upper()
    if not text or text in {"--", "-", "NA", "N/A"}:
        return None
    multiplier = 1.0
    if text.endswith("亿元"):
        multiplier = 100_000_000.0
        text = text[: -len("亿元")]
    elif text.endswith("亿"):
        multiplier = 100_000_000.0
        text = text[:-1]
    elif text.endswith("万元"):
        multiplier = 10_000.0
        text = text[: -len("万元")]
    elif text.endswith("万"):
        multiplier = 10_000.0
        text = text[:-1]
    elif text.endswith("CNY"):
        text = text[: -len("CNY")]
    elif text.endswith("RMB"):
        text = text[: -len("RMB")]
    elif text.endswith("元"):
        text = text[:-1]
    elif text.endswith("%"):
        text = text[:-1]
    return float(text.strip()) * multiplier


def _try_float(value: Any) -> float | None:
    try:
        return _float_or_none(value)
    except ValueError:
        return None


def _quarterly_tool_arguments(
    tool_name: str,
    ticker: str,
    start: str | None,
    end: str | None,
) -> dict[str, Any]:
    if tool_name not in QUERY_STYLE_TOOLS:
        return {"ticker": ticker, "start": start, "end": end}

    date_range = _period_range_text(start, end)
    return {
        "query": (
            f"获取 {ticker} 从 {start or '起始报告期'} 到 {end or '结束报告期'} 的季度财务数据。"
            "请优先返回结构化 JSON。字段包括：报告期、披露日期、是否累计口径、"
            "营业收入、营业成本、销售费用、管理费用、研发费用、财务费用、营业利润、"
            "归母净利润、扣非归母净利润、投资收益、公允价值变动、资产减值损失、"
            "信用减值损失、非经常性损益、经营活动现金流净额、资本开支、应收账款、"
            "存货、合同负债、总资产、总负债。请包含单位和数据来源。"
            "核心字段请使用 iFinD 单季度精确指标，必须同时返回且不要省略："
            "单季度.营业收入、单季度.营业成本、单季度.销售费用、单季度.管理费用、"
            "单季度.研发费用、单季度.财务费用、"
            "单季度.归属于母公司所有者的净利润、"
            "单季度.扣除非经常性损益后的归属母公司股东净利润、"
            "单季度.经营活动产生的现金流量净额。"
            f"报告期范围口径：{date_range}。"
        )
    }


def _high_frequency_tool_arguments(
    tool_name: str,
    ticker: str,
    start: str | None,
    end: str | None,
    factor_set: str | None,
) -> dict[str, Any]:
    if tool_name not in QUERY_STYLE_TOOLS:
        return {"ticker": ticker, "start": start, "end": end, "factor_set": factor_set}

    factor_text = {
        "catl": "新能源汽车销量、动力电池装机量、动力电池出口量、碳酸锂价格",
        "auto": "与目标公司经营相关的月度或周度行业高频指标",
    }.get(factor_set or "auto", factor_set or "相关行业高频指标")
    return {
        "query": (
            f"查询{factor_text}，时间范围{start or '2024-01'}至{end or '最新'}，"
            "优先返回月度数据，字段包含指标名称、日期、数值。"
        )
    }


def _highfreq_tool_arguments(
    tool_name: str,
    ticker: str,
    lookback_days: int,
    natural_query: str | None = None,
) -> dict[str, Any]:
    if natural_query:
        return {"query": natural_query}
    if tool_name not in QUERY_STYLE_TOOLS and "get_" not in tool_name:
        return {"ticker": ticker, "lookback_days": lookback_days}
    return {
        "query": (
            f"获取 {ticker} 近 {lookback_days} 天与基本面相关的非财务经营类高频数据和经营信号。"
            "请优先按日期返回时间截面表格或结构化 JSON。"
            "请覆盖：1. 需求与收入端：销量、出货、订单、中标、装机、产品价格。"
            "2. 成本端：碳酸锂、正极材料、电解液、隔膜、能源、运费、采购成本。"
            "3. 产业链：排产、开工率、库存、渠道库存、出口、储能项目。"
            "4. 风险端：政策、监管、关税、诉讼、处罚、停产、事故、重大负面舆情。"
            "不要只返回财务报表摘要。"
            "若返回 JSON，每条包含：date, signal_type, signal_name, value, unit, "
            "direction, evidence, source。"
            "方向 direction 只能是 positive, neutral, negative, unknown。"
        )
    }


def _period_range_text(start: str | None, end: str | None) -> str:
    if start and end:
        return f"从{_period_to_report_date(start)}到{_period_to_report_date(end)}"
    if end:
        return f"截至{_period_to_report_date(end)}"
    if start:
        return f"从{_period_to_report_date(start)}以来"
    return "最近8个报告期"


def _period_to_report_date(period: str) -> str:
    if len(period) == 6 and period[4] == "Q":
        month_day = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}[period[5]]
        return f"{period[:4]}-{month_day}"
    return period


def _period_from_value(value: Any) -> str:
    return normalize_report_period(value)


def _parse_markdown_table(answer: str) -> list[dict[str, Any]]:
    rows = [line for line in answer.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        raise IfindMcpResponseError("Unable to parse Markdown table from iFinD answer.")

    header = _split_markdown_row(rows[0])
    records: list[dict[str, Any]] = []
    for row in rows[2:]:
        cells = _split_markdown_row(row)
        if len(cells) != len(header):
            continue
        records.append(
            {
                _clean_column_name(name): cell.strip()
                for name, cell in zip(header, cells, strict=True)
            }
        )
    if not records:
        raise IfindMcpResponseError("Markdown table did not contain data rows.")
    return records


def _split_markdown_row(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _clean_column_name(value: str) -> str:
    return value.split("（单位")[0].split("(单位")[0].strip()
