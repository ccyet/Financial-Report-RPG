from __future__ import annotations

from pathlib import Path

from financial_report_rpg.rpg import (
    RpgJourney,
    RpgProgress,
    default_journey,
    load_progress,
    save_progress,
    summarize_progress,
    toggle_boss,
    toggle_task,
)

DISCLAIMER = "本应用用于财报阅读训练和研究过程记录，不构成投资建议。"
RPG_PROGRESS_PATH = Path(".local/rpg_progress.json")


def dashboard_tab_labels() -> list[str]:
    return ["RPG 旅程"]


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Financial Report RPG", layout="wide")
    st.title("Financial Report RPG")
    st.caption(DISCLAIMER)

    (rpg_tab,) = st.tabs(dashboard_tab_labels())
    with rpg_tab:
        _render_rpg_journey()

    st.caption(DISCLAIMER)


def _render_rpg_journey() -> None:
    import streamlit as st

    journey = default_journey()
    try:
        progress = load_progress(RPG_PROGRESS_PATH, journey)
    except ValueError as exc:
        st.error(f"RPG 进度读取失败：{exc}")
        return

    st.subheader("RPG 研究旅程")
    st.caption("把读财报拆成主线章节、每日副本、Boss 关卡和世界副本。")
    _render_rpg_status(progress, journey)
    _render_chapters(journey)
    _render_daily_tasks(progress, journey)
    _render_boss_tasks(progress, journey)
    _render_world_raid(progress, journey)

    if st.button("重置 RPG 进度", key="rpg_reset"):
        save_progress(RpgProgress(), RPG_PROGRESS_PATH)
        st.rerun()


def _render_rpg_status(progress: RpgProgress, journey: RpgJourney) -> None:
    import streamlit as st

    summary = summarize_progress(progress, journey)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("等级", f"Lv.{summary.level}/{summary.max_level} {summary.level_title}")
    k2.metric("研究经验", f"{summary.xp}/{summary.max_xp} XP")
    k3.metric("每日副本", f"{summary.daily_completed}/{summary.daily_total}")
    k4.metric("Boss 关卡", f"{summary.boss_completed}/{summary.boss_total}")
    st.progress(summary.xp / summary.max_xp if summary.max_xp else 0)
    st.caption(summary.level_description)
    badge_text = "、".join(summary.unlocked_badges) if summary.unlocked_badges else "暂无"
    st.info(f"已解锁徽章：{badge_text}")


def _render_chapters(journey: RpgJourney) -> None:
    import streamlit as st

    st.markdown("### 主线战役")
    chapter_cols = st.columns(4)
    for index, chapter in enumerate(journey.chapters):
        with chapter_cols[index % len(chapter_cols)]:
            st.markdown(f"**第 {index + 1} 章｜{chapter.title}**")
            st.caption(chapter.description)


def _render_daily_tasks(progress: RpgProgress, journey: RpgJourney) -> None:
    import streamlit as st

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


def _render_boss_tasks(progress: RpgProgress, journey: RpgJourney) -> None:
    import streamlit as st

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


def _render_world_raid(progress: RpgProgress, journey: RpgJourney) -> None:
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


if __name__ == "__main__":
    main()
