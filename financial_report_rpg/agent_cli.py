from __future__ import annotations

import argparse
from pathlib import Path

from financial_report_rpg.agent_journal import (
    DEFAULT_REPORT_DIR,
    GuidedCheckIn,
    complete_boss,
    complete_chapter,
    complete_task,
    next_check_in,
    record_note,
    save_reports,
)
from financial_report_rpg.rpg import (
    RpgProgress,
    default_journey,
    dungeon_progress,
    load_progress,
    save_progress,
    summarize_progress,
)

DEFAULT_PROGRESS_PATH = Path(".local/rpg_progress.json")


def run_command(
    argv: list[str],
    *,
    progress_path: str | Path = DEFAULT_PROGRESS_PATH,
    report_dir: str | Path = DEFAULT_REPORT_DIR,
) -> str:
    parser = _build_parser()
    args = parser.parse_args(argv)
    journey = default_journey()
    progress = load_progress(progress_path, journey)

    if args.command == "start":
        if args.dungeon:
            progress = progress.switch_dungeon(args.dungeon)
            save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _start_message(dungeon_progress(progress), journey)

    if args.command == "set-dungeon":
        progress = progress.switch_dungeon(args.dungeon)
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _start_message(dungeon_progress(progress), journey)

    if args.command == "status":
        save_reports(progress, journey, report_dir)
        return _status_message(dungeon_progress(progress), journey, report_dir)

    if args.command == "next":
        save_reports(progress, journey, report_dir)
        active = dungeon_progress(progress)
        return _guide_message(next_check_in(active, journey), active, journey)

    if args.command == "note":
        active = record_note(
            dungeon_progress(progress),
            args.text,
            tags=args.tag,
            linked_chapter_id=args.chapter,
            linked_task_id=args.task,
            linked_boss_id=args.boss,
            journey=journey,
        )
        progress = _store_active(progress, active)
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _status_message(active, journey, report_dir, prefix="已记录")

    if args.command == "complete-chapter":
        active = complete_chapter(dungeon_progress(progress), args.chapter_id, journey)
        if args.note:
            active = record_note(
                active,
                args.note,
                linked_chapter_id=args.chapter_id,
                journey=journey,
            )
        progress = _store_active(progress, active)
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _settlement_message(active, journey, "主线关卡已点亮")

    if args.command == "complete-task":
        active = complete_task(dungeon_progress(progress), args.task_id, journey)
        if args.note:
            active = record_note(
                active,
                args.note,
                linked_task_id=args.task_id,
                journey=journey,
            )
        progress = _store_active(progress, active)
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _settlement_message(active, journey, "每日副本已打卡")

    if args.command == "complete-boss":
        active = complete_boss(dungeon_progress(progress), args.boss_id, journey)
        if args.note:
            active = record_note(
                active,
                args.note,
                linked_boss_id=args.boss_id,
                journey=journey,
            )
        progress = _store_active(progress, active)
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _settlement_message(active, journey, "Boss 关卡已通关")

    if args.command == "export":
        save_reports(progress, journey, report_dir)
        return _status_message(
            dungeon_progress(progress), journey, report_dir, prefix="已导出", show_paths=True
        )

    raise ValueError(f"unknown command: {args.command}")


def main() -> None:
    print(run_command(_argv_without_program()))


def _argv_without_program() -> list[str]:
    import sys

    return sys.argv[1:]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="financial-report-rpg")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--dungeon")

    set_dungeon = subparsers.add_parser("set-dungeon")
    set_dungeon.add_argument("dungeon")

    subparsers.add_parser("status")
    subparsers.add_parser("next")

    note = subparsers.add_parser("note")
    note.add_argument("--text", required=True)
    note.add_argument("--tag", action="append", default=[])
    note.add_argument("--chapter")
    note.add_argument("--task")
    note.add_argument("--boss")

    complete_chapter_parser = subparsers.add_parser("complete-chapter")
    complete_chapter_parser.add_argument("chapter_id")
    complete_chapter_parser.add_argument("--note")

    complete_task_parser = subparsers.add_parser("complete-task")
    complete_task_parser.add_argument("task_id")
    complete_task_parser.add_argument("--note")

    complete_boss_parser = subparsers.add_parser("complete-boss")
    complete_boss_parser.add_argument("boss_id")
    complete_boss_parser.add_argument("--note")

    subparsers.add_parser("export")
    return parser


def _status_message(
    progress,
    journey,
    report_dir: str | Path,
    *,
    prefix: str = "当前状态",
    show_paths: bool = False,
) -> str:
    summary = summarize_progress(progress, journey)
    report_path = Path(report_dir)
    message = (
        f"{prefix}：{summary.level_title}，"
        f"等级 {summary.level}/{summary.max_level}，"
        f"{summary.xp}/{summary.max_xp} XP，"
        f"主线 {summary.chapter_completed}/{summary.chapter_total}，"
        f"每日副本 {summary.daily_completed}/{summary.daily_total}，"
        f"Boss {summary.boss_completed}/{summary.boss_total}。"
    )
    if show_paths:
        return f"{message}报告：{report_path / 'progress.md'}；{report_path / 'progress.html'}"
    return message


def _store_active(progress: RpgProgress, active: RpgProgress) -> RpgProgress:
    if not active.active_dungeon:
        return active
    return progress.with_dungeon(active.active_dungeon, active)


def _start_message(progress, journey) -> str:
    summary = summarize_progress(progress, journey)
    gate = next_check_in(progress, journey)
    dungeon = progress.active_dungeon or "未选择"
    return (
        "读取存档：旧卷轴已经展开。"
        f"等级 {summary.level}/{summary.max_level}，称号 {summary.level_title}。"
        f"本次挑战副本：{dungeon}。"
        f"副本进度：主线 {summary.chapter_completed}/{summary.chapter_total}，"
        f"每日副本 {summary.daily_completed}/{summary.daily_total}，"
        f"Boss {summary.boss_completed}/{summary.boss_total}。"
        f"当前关卡：{gate.title}。"
        f"引导问题：{gate.prompt}"
        "确认本次是否挑战该副本，或告诉我要切换行业副本。"
    )


def _settlement_message(progress, journey, title: str) -> str:
    summary = summarize_progress(progress, journey)
    gate = next_check_in(progress, journey)
    dungeon = progress.active_dungeon or "未选择"
    return (
        f"关卡结算：{title}。"
        f"副本：{dungeon}。"
        f"等级 {summary.level}/{summary.max_level}，称号 {summary.level_title}。"
        f"主线 {summary.chapter_completed}/{summary.chapter_total}，"
        f"每日副本 {summary.daily_completed}/{summary.daily_total}，"
        f"Boss {summary.boss_completed}/{summary.boss_total}。"
        f"下一关：{gate.title}。"
        "若当前终端支持图片，请发送 HTML 等级与进度截图；"
        "否则以本段结算作为状态面板。"
    )


def _guide_message(
    gate: GuidedCheckIn,
    progress,
    journey,
) -> str:
    summary = summarize_progress(progress, journey)
    criteria = "；".join(criterion.rstrip("。") for criterion in gate.pass_criteria)
    dungeon = progress.active_dungeon or "未选择"
    return (
        f"副本：{dungeon}。"
        f"当前关卡：{gate.title}。"
        f"引导问题：{gate.prompt} "
        f"通关标准：{criteria}。"
        f"打卡命令：{gate.completion_command}。"
        f"等级 {summary.level}/{summary.max_level}，"
        f"进度：主线 {summary.chapter_completed}/{summary.chapter_total}，"
        f"每日副本 {summary.daily_completed}/{summary.daily_total}，"
        f"Boss {summary.boss_completed}/{summary.boss_total}。"
    )


if __name__ == "__main__":
    main()
