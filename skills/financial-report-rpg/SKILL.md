---
name: financial-report-rpg
description: workspace 兼容入口；用 AI 对话驱动财报阅读 RPG，按关卡检验标准打卡升级并导出汇报
when_to_use: 用户要通过对话读财报、记录研究想法、推进 RPG 关卡、生成当前进度汇报，或准备同步 Notion 时
version: 2026.05.10
---

# Workspace 兼容入口

这是给会扫描 `<workspace>/skills/` 的终端 agent 使用的入口。完整发布说明在仓库根目录 `SKILL.md`。

# 使用方式

- 从包含 `pyproject.toml` 的仓库根目录运行命令。
- 不要只复制 `skills/financial-report-rpg/`；这个 skill 依赖仓库里的 `financial_report_rpg` Python 模块。
- 进度文件写入 `.local/rpg_progress.json`，导出文件写入 `.local/rpg_exports/`。
- 不联网抓财报，不伪造数据，不给投资建议。
- 不要要求用户打开 Streamlit；Streamlit 只是可选查看器，不是主流程。

# 对话流程

1. 用 `uv run python -m financial_report_rpg.agent_cli next` 获取当前关卡、引导问题和通关标准。
2. 用户回答后，先用 `note` 保存原始想法。
3. 按通关标准判断是否打卡；不满足标准只追问一个关键缺口。
4. 主线用 `complete-chapter`，每日副本用 `complete-task`，Boss 用 `complete-boss`。
5. 每次状态变化后运行 `export`，生成文本和 HTML 进度报告。

对应 Python 接口包括 `record_note`、`next_check_in`、`generate_html_report` 和 `build_notion_export`。Notion 只作为预留接口，用户提供自己的数据库或页面后再写入。

# 常用命令

```bash
uv run python -m financial_report_rpg.agent_cli status
uv run python -m financial_report_rpg.agent_cli next
uv run python -m financial_report_rpg.agent_cli note --text "记录一条研究想法" --tag "现金流"
uv run python -m financial_report_rpg.agent_cli complete-chapter first_impression --note "初始印象已完成"
uv run python -m financial_report_rpg.agent_cli complete-task cash --note "现金流副本已完成"
uv run python -m financial_report_rpg.agent_cli complete-boss three_year_map --note "三年财报地图已完成"
uv run python -m financial_report_rpg.agent_cli export
```

# 输出格式

每轮状态更新后，优先给当前关卡、通关标准、本轮是否通过、缺口或打卡结果，以及 `.local/rpg_exports/progress.md` / `.local/rpg_exports/progress.html`。
