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
uv run python -m financial_report_rpg.agent_cli doctor
uv run python -m financial_report_rpg.agent_cli start --dungeon "动力电池峡谷"
```

你会看到存档进度、等级、当前行业副本、当前关卡和引导问题。确认副本后，继续查看关卡标准：

```bash
uv run python -m financial_report_rpg.agent_cli next
```

切换行业副本时：

```bash
uv run python -m financial_report_rpg.agent_cli start --dungeon "半导体矿洞"
```

半导体矿洞会拥有独立进度，不会继承动力电池峡谷的关卡完成状态。

## 下载财报资料

用户指定上市公司后，可先下载巨潮网资料：

```bash
uv run python -m financial_report_rpg.agent_cli download-reports 300750
uv run python -m financial_report_rpg.agent_cli list-docs 300750
```

该命令会下载招股说明书和 2022 年至今的年度、半年度、一季度、三季度报告。输出只显示资料背包结算，不向用户展示本地绝对路径。

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

## 查看结算面板

```bash
uv run python -m financial_report_rpg.agent_cli panel
```

不支持图片的终端应优先展示这个面板，而不是展示本地文件路径。

## 导出当前进度

```bash
uv run python -m financial_report_rpg.agent_cli export
```

`.local/` 是个人存档目录，不应提交到 Git。

导出命令会刷新本地文本和 HTML 进度报告，但 agent 不应把具体路径直接抛给用户；如果终端支持图片，展示 HTML 的等级与进度截图，否则用游戏风格文字结算。
