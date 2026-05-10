# Fundamental Pulse

轻量 Python MVP，用于把季度财务数据转成可测试的基本面增长判断。

## Quick start

```bash
uv run pulse analyze 300750.SZ --mock --period 2025Q4
```

像素 RPG 财报阅读方案页可直接打开 `financial_rpg_plan.html` 查看。

油气股可显式传入油价边界、利润敏感度和估值倍数：

```bash
uv run pulse analyze 300750.SZ --mock --period 2025Q4 \
  --industry oil-gas \
  --base-oil-price 80 \
  --oil-price-floor 60 \
  --oil-price-ceiling 100 \
  --profit-sensitivity-per-usd 2 \
  --valuation-multiple-low 8 \
  --valuation-multiple-high 12
```

宁德时代这类公司可传入高频因子集合，输出公司相关因子与季度指标的相关性，
并基于下一季度已可见高频数据形成经营前瞻：

```bash
uv run pulse analyze 300750.SZ --mock --period 2025Q4 \
  --factor-set catl \
  --target-metric revenue_yoy \
  --max-lag-quarters 1
```

真实 iFinD MCP 接入时，不要使用 `--mock`。推荐用 JSON 配置文件传入，
复制 `ifind.mcp.example.json` 为本地 `ifind.mcp.json` 后填写认证信息：

```bash
cp ifind.mcp.example.json ifind.mcp.json
uv run pulse ifind ping
uv run pulse ifind tools
```

当前已验证的默认配置是：财报数据走 `hexin-ifind-ds-stock-mcp` 的
`get_stock_financials`。iFinD MCP 的 skills 类工具可用自然语句通过 `query`
调用；高频经营数据可用 `--highfreq-query` 或 `pull-highfreq --query` 传入。

如果要拉非财务经营类时间截面，优先用 EDB skills 工具：

```bash
uv run pulse ifind-tools --ifind-config ifind.mcp.json --ifind-server hexin-ifind-ds-edb-mcp
uv run pulse ifind pull-highfreq 300750.SZ \
  --ifind-high-frequency-server hexin-ifind-ds-edb-mcp \
  --ifind-high-frequency-tool get_edb_data \
  --query '查询最近12个月新能源汽车销量、动力电池装机量、碳酸锂价格，按日期返回表格，字段包含日期、指标名称、数值、单位。' \
  --save-raw
uv run pulse analyze 300750.SZ --source ifind --start 2022Q1 --end 2025Q4 \
  --with-highfreq \
  --ifind-high-frequency-server hexin-ifind-ds-edb-mcp \
  --ifind-high-frequency-tool get_edb_data \
  --highfreq-query '查询最近12个月新能源汽车销量、动力电池装机量、碳酸锂价格，按日期返回表格，字段包含日期、指标名称、数值、单位。'
```

配置后运行：

```bash
uv run pulse ifind pull-quarterly 300750.SZ --start 2022Q1 --end 2024Q4 --save-raw
uv run pulse analyze 300750.SZ --source ifind --start 2022Q1 --end 2024Q4
```

也支持环境变量部署：

```bash
IFIND_MCP_URL=
IFIND_MCP_API_KEY=
IFIND_MCP_FINANCIAL_TOOL=get_stock_financials
IFIND_MCP_TIMEOUT_SECONDS=60
PULSE_SOURCE=mock
```

本地 `ifind.mcp.json`、`.env` 和 `data/raw/` 默认不会入库。`pull-quarterly --save-raw`
只保存脱敏后的原始响应，不保存 Authorization、token、session、cookie 或账号标识。

报告输出到 `reports/{ticker}_{period}.md`。
每次运行还会追加记录到 `reports/index.json`，并在 `reports/runs/` 保存一份带
`run_id` 的历史报告副本。

## Workflow service

产品化入口是 `run_analysis(request)`，Streamlit 和 CLI 都复用这条链路，不重复写业务计算：

```python
from fundamental_pulse.models import AnalysisRequest
from fundamental_pulse.workflow import run_analysis

result = run_analysis(
    AnalysisRequest(
        ticker="300750.SZ",
        source="mock",
        with_highfreq=True,
        thesis_file="examples/thesis/300750.yml",
    )
)
```

轻量页面：

```bash
uv run streamlit run fundamental_pulse/app/streamlit_app.py
```

页面只负责参数输入、KPI 摘要、观察列表表格、历史报告读取和完整报告展示；
分析计算仍由 `run_analysis` 完成。

## Watchlist dashboard

观察列表使用本地 YAML 文件维护，示例在 `examples/watchlists/core_a_share.yml`。
批量运行命令：

```bash
uv run pulse watchlist run examples/watchlists/core_a_share.yml --mock --limit 1
```

批量运行会逐项调用 `run_analysis`。单个股票配置错误会记录为该项失败，不会中断整个
观察列表。页面中的观察列表和历史报告均以表格展示，完整报告默认放在折叠区域中。

## Thesis verification

投资假设用本地 YAML/JSON 文件维护，示例在 `examples/thesis/300750.yml`。
验证命令：

```bash
uv run pulse thesis verify 300750.SZ --thesis-file examples/thesis/300750.yml --mock
```

也可以在季度报告中同时输出假设验证：

```bash
uv run pulse analyze 300750.SZ --mock --with-highfreq --thesis-file examples/thesis/300750.yml
```

thesis 文件中的 `ticker` 必须与 CLI 股票代码一致。未传入高频信号时，高频 driver
会标记为 `unknown`，不会让命令失败。

## Scope

- 使用 mock iFinD MCP adapter 跑通链路。
- 真实 iFinD MCP adapter 支持环境变量或 JSON 配置文件，按 tool discovery 或配置项拉取季度财务数据。
- 财务计算全部使用确定性代码。
- 数据验证会提示缺失核心字段、重复期间、非经常性损益勾稽异常和收入质量风险。
- 高频因子相关性会把因子按季度聚合，计算与目标财务指标的同步/领先相关系数。
- 未来季度经营判断会比较下一季度高频因子和当前季度的变化，输出改善、走弱、平稳或数据不足。
- 投资假设验证读取本地 YAML/JSON 文件，只输出 driver 状态和汇总状态。
- 油气业务判断使用显式假设计算利润中枢和估值边界，不内置真实投资判断。
- 输出仅用于研究记录，不构成投资建议。

## Final report format

传入高频因子并形成前瞻判断时，报告固定采用结论先行格式：

```text
# {ticker} {forecast_period} 未来季度经营判断

## 最终结论
- 判断
- 置信度
- 预测季度
- 观察基准
- 目标指标
- 结论

## 核心信号
## 数据验证
## 财务底稿
## 高频因子相关性
## 利润归因
## 风险与反证信号
## 跟踪动作
## 数据来源与口径
```

没有下一季度高频数据时，前瞻判断必须输出“数据不足”，不伪造判断。
