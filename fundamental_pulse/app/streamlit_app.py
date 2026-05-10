from __future__ import annotations

from pathlib import Path
from typing import Any

from fundamental_pulse.app.formatting import (
    build_history_table,
    build_result_kpis,
    build_watchlist_table,
    format_date,
    format_error_summary,
)
from fundamental_pulse.models import AnalysisRequest, AnalysisRunResult
from fundamental_pulse.report_store import load_report_history, read_report
from fundamental_pulse.rpg import (
    RpgProgress,
    default_journey,
    load_progress,
    save_progress,
    summarize_progress,
    toggle_boss,
    toggle_task,
)
from fundamental_pulse.watchlist import load_watchlist, run_watchlist
from fundamental_pulse.workflow import run_analysis

DISCLAIMER = "本页面和报告仅用于研究记录，不构成投资建议。"
RPG_PROGRESS_PATH = Path(".local/rpg_progress.json")


def dashboard_tab_labels() -> list[str]:
    return ["单股分析", "观察列表", "RPG 旅程", "历史报告"]


def format_history_label(entry: dict[str, Any]) -> str:
    created_at = format_date(str(entry.get("created_at") or ""))
    ticker = str(entry.get("ticker") or "unknown")
    period = str(entry.get("period") or "unknown")
    source = str(entry.get("source") or "unknown")
    classification = str(entry.get("classification") or "unknown")
    return f"{created_at} | {ticker} | {period} | {source} | {classification}"


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Fundamental Pulse", layout="wide")
    st.title("Fundamental Pulse Dashboard")
    st.caption(DISCLAIMER)

    single_tab, watchlist_tab, rpg_tab, history_tab = st.tabs(dashboard_tab_labels())
    with single_tab:
        _render_single_analysis()
    with watchlist_tab:
        _render_watchlist()
    with rpg_tab:
        _render_rpg_journey()
    with history_tab:
        _render_history()

    st.caption(DISCLAIMER)


def _render_single_analysis() -> None:
    import streamlit as st

    st.subheader("单股分析")
    col1, col2, col3 = st.columns([1.2, 1, 1])
    ticker = col1.text_input("股票代码", value="300750.SZ", key="single_ticker")
    source = col2.selectbox("数据源", options=["mock", "ifind"], index=0, key="single_source")
    period_text = col3.text_input(
        "报告期",
        value="",
        key="single_period",
        help="可填单季度 2025Q4，也可填区间 2023Q1-2025Q4。",
    )

    col4, col5, col6 = st.columns(3)
    start_text = col4.text_input("开始季度", value="", key="single_start")
    end_text = col5.text_input("结束季度", value="", key="single_end")
    lookback_days = col6.number_input(
        "高频回看天数",
        min_value=1,
        value=90,
        step=10,
        key="single_lookback",
    )

    with_highfreq = st.checkbox("启用 highfreq", value=False, key="single_highfreq")
    use_thesis = st.checkbox("启用 thesis", value=False, key="single_thesis_enabled")
    thesis_file = None
    if use_thesis:
        thesis_file = _none_if_blank(
            st.text_input("thesis 文件", value="examples/thesis/300750.yml")
        )

    if st.button("运行单股分析", type="primary"):
        try:
            period, start, end = parse_single_period_inputs(
                period_text=period_text,
                start_text=start_text,
                end_text=end_text,
            )
            result = run_analysis(
                AnalysisRequest(
                    ticker=ticker.strip(),
                    source=source,
                    period=period,
                    start=start,
                    end=end,
                    with_highfreq=with_highfreq,
                    lookback_days=int(lookback_days),
                    thesis_file=Path(thesis_file) if thesis_file else None,
                )
            )
        except Exception as exc:
            _render_error(exc)
            return
        _render_analysis_result(result)


def _render_watchlist() -> None:
    import streamlit as st

    st.subheader("观察列表批量分析")
    col1, col2, col3 = st.columns([2, 1, 1])
    watchlist_path = col1.text_input(
        "watchlist 文件",
        value="examples/watchlists/core_a_share.yml",
    )
    source = col2.selectbox("数据源", options=["mock", "ifind"], index=0, key="watchlist_source")
    limit = col3.number_input("运行数量上限", min_value=1, value=1, step=1)

    if st.button("运行观察列表", type="primary"):
        try:
            watchlist = load_watchlist(watchlist_path)
            result = run_watchlist(
                watchlist,
                mock=source == "mock",
                source=source,
                limit=int(limit),
            )
        except Exception as exc:
            _render_error(exc)
            return

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("运行状态", "完成")
        k2.metric("合计", str(result.total))
        k3.metric("成功", str(result.succeeded))
        k4.metric("失败", str(result.failed))
        st.dataframe(build_watchlist_table(result), width="stretch", hide_index=True)
        for item in result.items:
            if item.status == "failed":
                summary, detail = format_error_summary(item.error_detail or item.error_summary)
                st.warning(f"{item.ticker}：{summary}")
                with st.expander(f"{item.ticker} 错误详情"):
                    st.code(detail)


def _render_rpg_journey() -> None:
    import streamlit as st

    journey = default_journey()
    try:
        progress = load_progress(RPG_PROGRESS_PATH, journey)
    except ValueError as exc:
        _render_error(exc)
        return

    st.subheader("RPG 研究旅程")
    st.caption("把读财报拆成主线章节、每日副本、Boss 关卡和世界副本。")
    _render_rpg_status(progress, journey)

    st.markdown("### 主线战役")
    chapter_cols = st.columns(4)
    for index, chapter in enumerate(journey.chapters):
        with chapter_cols[index % len(chapter_cols)]:
            st.markdown(f"**第 {index + 1} 章｜{chapter.title}**")
            st.caption(chapter.description)

    st.markdown("### 每日副本")
    task_cols = st.columns(3)
    for index, task in enumerate(journey.daily_tasks):
        with task_cols[index % len(task_cols)]:
            completed = task.id in progress.completed_tasks
            st.markdown(f"**{task.title}**")
            st.caption(task.description)
            st.caption(f"{task.xp} XP")
            label = "取消打卡" if completed else "打卡"
            if st.button(label, key=f"rpg_task_{task.id}", type="secondary"):
                progress = toggle_task(progress, task.id, journey)
                save_progress(progress, RPG_PROGRESS_PATH)
                st.rerun()

    st.markdown("### Boss 关卡")
    boss_cols = st.columns(4)
    for index, boss in enumerate(journey.boss_tasks):
        with boss_cols[index % len(boss_cols)]:
            completed = boss.id in progress.completed_bosses
            st.markdown(f"**{boss.title}**")
            st.caption(boss.description)
            label = "取消通关" if completed else "标记通关"
            if st.button(label, key=f"rpg_boss_{boss.id}"):
                progress = toggle_boss(progress, boss.id, journey)
                save_progress(progress, RPG_PROGRESS_PATH)
                st.rerun()

    _render_world_raid(progress, journey)
    if st.button("重置 RPG 进度", key="rpg_reset"):
        save_progress(RpgProgress(), RPG_PROGRESS_PATH)
        st.rerun()


def _render_rpg_status(progress: RpgProgress, journey: Any) -> None:
    import streamlit as st

    summary = summarize_progress(progress, journey)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("等级", summary.level_title)
    k2.metric("研究经验", f"{summary.xp}/{summary.max_xp} XP")
    k3.metric("每日副本", f"{summary.daily_completed}/{summary.daily_total}")
    k4.metric("Boss 关卡", f"{summary.boss_completed}/{summary.boss_total}")
    st.progress(summary.xp / summary.max_xp if summary.max_xp else 0)
    st.caption(summary.level_description)
    badge_text = "、".join(summary.unlocked_badges) if summary.unlocked_badges else "暂无"
    st.info(f"已解锁徽章：{badge_text}")


def _render_world_raid(progress: RpgProgress, journey: Any) -> None:
    import streamlit as st

    summary = summarize_progress(progress, journey)
    st.markdown("### 世界副本")
    if summary.world_raid_unlocked:
        st.success(f"{journey.world_raid.title} 已解锁")
        st.write(journey.world_raid.description)
        return
    st.warning(
        f"还需完成 {journey.world_raid.unlock_required_bosses - summary.boss_completed} "
        f"个 Boss 关卡，才能解锁 {journey.world_raid.title}。"
    )


def _render_history() -> None:
    import streamlit as st

    st.subheader("历史报告")
    history = load_report_history()
    if not history:
        st.info("暂无历史报告。")
        return

    st.dataframe(build_history_table(history), width="stretch", hide_index=True)
    labels = [format_history_label(entry) for entry in history]
    selected_label = st.selectbox("选择历史报告", labels)
    selected = history[labels.index(selected_label)]
    report_path = selected.get("archive_report_path") or selected.get("report_path")
    if not report_path:
        st.warning("该历史记录缺少报告路径。")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("报告期", str(selected.get("period") or "NA"))
    col2.metric("增长性质", str(selected.get("classification") or "NA"))
    col3.metric("数据源", str(selected.get("source") or "NA"))
    col4.metric("运行状态", "已归档")

    try:
        report = read_report(str(report_path))
    except FileNotFoundError:
        st.warning(f"报告文件不存在：{report_path}")
        return
    with st.expander("完整报告", expanded=False):
        st.markdown(report)


def _render_analysis_result(result: AnalysisRunResult) -> None:
    import streamlit as st

    kpis = build_result_kpis(result)
    cols = st.columns(len(kpis))
    for col, (label, value) in zip(cols, kpis.items(), strict=True):
        col.metric(label, value)

    if result.highfreq_summary:
        st.info(result.highfreq_summary)
    if result.thesis_status:
        st.info(f"投资假设验证：{result.thesis_status}")
    with st.expander("完整报告", expanded=False):
        st.markdown(result.report)


def _render_error(exc: Exception) -> None:
    import streamlit as st

    summary, detail = format_error_summary(str(exc))
    st.error(f"运行失败：{summary}")
    with st.expander("错误详情"):
        st.code(detail)


def _none_if_blank(value: str) -> str | None:
    text = value.strip()
    return text or None


def parse_single_period_inputs(
    period_text: str,
    start_text: str,
    end_text: str,
) -> tuple[str | None, str | None, str | None]:
    period = _none_if_blank(period_text)
    start = _none_if_blank(start_text)
    end = _none_if_blank(end_text)
    if period is None:
        return None, start, end

    normalized = period.replace("至", "-").replace("—", "-").replace("～", "-").replace("~", "-")
    if "-" not in normalized:
        return period, start, end

    left, right = [part.strip() for part in normalized.split("-", 1)]
    return None, start or left or None, end or right or None


if __name__ == "__main__":
    main()
