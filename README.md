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
- “本次挑战半导体矿洞”
- “记录：宁德时代现金流比利润更值得先核对”
- “我回答完了，按标准看能不能打卡”
- “完成现金流副本，笔记是经营现金流和净利润要放一起看”
- “导出当前进度”
- “下载宁德时代的招股说明书和 2022 年至今财报”
- “打开结算面板”

AI 应把状态保存到 `.local/rpg_progress.json`，并同步生成：

- `.local/rpg_exports/progress.md`
- `.local/rpg_exports/progress.html`

导出命令只刷新本地进度报告；面向用户回复时不展示具体存储路径。

## 本地命令

所有命令都从仓库根目录运行：

```bash
uv run python -m financial_report_rpg.agent_cli doctor
uv run python -m financial_report_rpg.agent_cli start
uv run python -m financial_report_rpg.agent_cli start --dungeon "动力电池峡谷"
uv run python -m financial_report_rpg.agent_cli download-reports 300750
uv run python -m financial_report_rpg.agent_cli list-docs 300750
uv run python -m financial_report_rpg.agent_cli status
uv run python -m financial_report_rpg.agent_cli next
uv run python -m financial_report_rpg.agent_cli set-dungeon "半导体矿洞"
uv run python -m financial_report_rpg.agent_cli note --text "先记录一条研究假设" --tag "假设"
uv run python -m financial_report_rpg.agent_cli complete-chapter first_impression --note "初始印象已完成"
uv run python -m financial_report_rpg.agent_cli complete-task cash --note "现金流副本已完成"
uv run python -m financial_report_rpg.agent_cli panel
uv run python -m financial_report_rpg.agent_cli export
```

一个行业就是一个副本。不同行业副本的主线、每日、Boss 和笔记进度彼此独立；切换副本不会清空其他行业的存档。

## 巨潮财报下载

`download-reports` 会从巨潮网按股票代码或证券简称解析上市公司，并下载：

- 招股说明书。
- 2022 年至今的年度报告、半年度报告、一季度报告、三季度报告。

示例：

```bash
uv run python -m financial_report_rpg.agent_cli download-reports 300750
uv run python -m financial_report_rpg.agent_cli download-reports 宁德时代 --from-year 2022
uv run python -m financial_report_rpg.agent_cli list-docs 宁德时代
```

下载后会生成本地资料清单，重复运行会跳过已下载 PDF。命令输出只返回资料背包结算，不展示本地绝对路径。下载失败会明确列出失败标题和错误原因。

## 推荐流程

1. `doctor`：先检查运行环境、存档和巨潮连通性。
2. `start --dungeon "<行业副本>"`：进入当前行业副本。
3. `download-reports <股票代码或简称>`：准备资料背包并绑定到当前副本。
4. `next`：读取当前关卡问题和通关标准。
5. `note`：记录用户原始想法。
6. `complete-chapter` / `complete-task` / `complete-boss`：满足标准后打卡。
7. `panel`：输出不含路径的结算面板；终端支持图片时再展示 HTML 截图。
8. `export`：刷新本地文本和 HTML 进度报告。

## RPG 结构

- 主线战役：7 个章节，每章都有引导问题和通关标准。
- 每日副本：6 个轻量打卡任务，完成后获得 XP 和徽章。
- Boss 关卡：4 个阶段性输出，必须满足检验标准后才通关。
- 世界副本：研究产业在国家价值链中的位置。
- 进度上限：等级 175，主线 50，Boss 99。

关卡结束时，agent 不应向用户展示存储路径；优先用游戏结算语气输出等级、主线进度、Boss 进度。若当前终端支持图片，应展示 HTML 等级与进度区域截图；不支持图片时，用文字状态面板替代。

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

- 只接入巨潮网公告下载，不接外部行情服务。
- 不伪造财报数据，不自动替用户编造财报结论。
- 不构成投资建议。
