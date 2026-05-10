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
uv run python -m financial_report_rpg.agent_cli next
```

你会看到当前关卡、引导问题、通关标准和打卡命令。

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
