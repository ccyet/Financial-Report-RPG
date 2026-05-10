# Minimal Run

这个示例面向外部用户，假设你已经克隆仓库并安装依赖：

```bash
git clone https://github.com/ccyet/Financial-Report-RPG.git
cd Financial-Report-RPG
uv sync
```

## 在终端 agent 里启动

对支持 skills 的 agent 说：

```text
开启 financial-report-rpg，给我当前关卡。
```

agent 应先读取 `SKILL.md`，再从仓库根目录运行：

```bash
uv run python -m financial_report_rpg.agent_cli start --dungeon "动力电池峡谷"
```

你会看到存档进度、等级、当前行业副本、当前关卡和引导问题。确认副本后，继续查看关卡标准：

```bash
uv run python -m financial_report_rpg.agent_cli next
```

## 记录一次回答

```bash
uv run python -m financial_report_rpg.agent_cli note \
  --text "这家公司初步看是卖动力电池给整车厂，位置在新能源车产业链中游，待验证客户集中度。" \
  --tag "初始印象"
```

## 通过主线第一关

当回答满足通关标准后：

```bash
uv run python -m financial_report_rpg.agent_cli complete-chapter first_impression \
  --note "已完成初始印象：业务、客户、产业位置和待验证问题齐备。"
```

## 导出当前进度

```bash
uv run python -m financial_report_rpg.agent_cli export
```

输出文件：

- `.local/rpg_exports/progress.md`
- `.local/rpg_exports/progress.html`

`.local/` 是个人存档目录，不应提交到 Git。

关卡结束时，agent 不应把这些路径直接抛给用户；如果终端支持图片，展示 HTML 的等级与进度截图，否则用游戏风格文字结算。
