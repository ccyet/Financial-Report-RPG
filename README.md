# Financial Report RPG

一个 AI-native 的财报阅读 RPG：用户通过对话记录研究想法、完成任务、升级、存档，并导出当前进度 HTML 和文本汇报。

## 外部用户安装

```bash
git clone https://github.com/ccyet/Financial-Report-RPG.git
cd Financial-Report-RPG
uv sync
```

这个仓库本身就是一个可加载的 agent skill：

- 根目录 `SKILL.md`：适合把整个仓库安装为 OpenClaw / OpenCode 等终端 agent 的 skill。
- `skills/financial-report-rpg/SKILL.md`：适合把本仓库作为 workspace 时，被 `<workspace>/skills/` 扫描到。

不要只复制 `skills/financial-report-rpg/`，因为运行命令依赖仓库里的 `financial_report_rpg/` Python 模块和 `pyproject.toml`。

OpenClaw 可用以下命令检查：

```bash
openclaw skills list
openclaw skills info financial-report-rpg
openclaw skills check
```

如果更新后没有生效，新开会话或重启 gateway：

```bash
openclaw gateway restart
```

## 核心方式

把这个仓库放进支持文件读写和命令执行的 AI 工作区后，直接和 AI 对话：

- “开启财报 RPG，给我当前关卡”
- “记录：宁德时代现金流比利润更值得先核对”
- “我回答完了，按标准看能不能打卡”
- “完成现金流副本，笔记是经营现金流和净利润要放一起看”
- “导出当前进度”

AI 应把状态保存到 `.local/rpg_progress.json`，并同步生成：

- `.local/rpg_exports/progress.md`
- `.local/rpg_exports/progress.html`

## 本地命令

所有命令都从仓库根目录运行：

```bash
uv run python -m financial_report_rpg.agent_cli status
uv run python -m financial_report_rpg.agent_cli next
uv run python -m financial_report_rpg.agent_cli note --text "先记录一条研究假设" --tag "假设"
uv run python -m financial_report_rpg.agent_cli complete-chapter first_impression --note "初始印象已完成"
uv run python -m financial_report_rpg.agent_cli complete-task cash --note "现金流副本已完成"
uv run python -m financial_report_rpg.agent_cli export
```

## RPG 结构

- 主线战役：7 个章节，每章都有引导问题和通关标准。
- 每日副本：6 个轻量打卡任务，完成后获得 XP 和徽章。
- Boss 关卡：4 个阶段性输出，必须满足检验标准后才通关。
- 世界副本：研究产业在国家价值链中的位置。

## 可选查看器

Streamlit 只作为可选查看器，不是主流程：

```bash
uv run streamlit run financial_report_rpg/app/streamlit_app.py
```

## Notion 预留

`build_notion_export` 会生成 Notion connector 可用的标题、属性和 Markdown。只有用户提供自己的 Notion 数据库或页面后，才同步远程存档；默认只做本地文件存档。

## 最小示例

见 `examples/MINIMAL-RUN.md`。

## 方案页

`financial_rpg_plan.html` 是早期方案解读页，可直接用浏览器打开。

## 验证

```bash
uv run pytest -q
uv run ruff check .
```

## 边界

- 不接外部行情或财报服务。
- 不伪造财报数据或联网抓取。
- 不构成投资建议。
