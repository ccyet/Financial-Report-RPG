# Financial Report RPG

一个纯 RPG 化的财报阅读训练应用。

当前目标是把“读财报”拆成可打卡、可升级、可解锁的研究旅程。

## 使用

```bash
uv run streamlit run financial_report_rpg/app/streamlit_app.py
```

打开页面后进入 `RPG 旅程`：

- 主线战役：7 个章节，从初始印象到画像确认和灵感沉淀。
- 每日副本：6 个轻量任务，点击打卡后获得 XP 和徽章。
- Boss 关卡：4 个阶段性输出，完成后解锁世界副本。
- 世界副本：研究产业在国家价值链中的位置。

进度保存在本地 `.local/rpg_progress.json`，不会提交到仓库。

## 方案页

`financial_rpg_plan.html` 是早期方案解读页，可直接用浏览器打开。

## 验证

```bash
uv run pytest -q
uv run ruff check .
```

## 边界

- 不接外部行情或财报服务。
- 只保留 RPG 进度训练通路。
- 不构成投资建议。
