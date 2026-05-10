from __future__ import annotations

import argparse
from pathlib import Path

from financial_report_rpg.agent_journal import (
    DEFAULT_REPORT_DIR,
    complete_boss,
    complete_task,
    record_note,
    save_reports,
)
from financial_report_rpg.rpg import (
    default_journey,
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

    if args.command == "status":
        save_reports(progress, journey, report_dir)
        return _status_message(progress, journey, report_dir)

    if args.command == "note":
        progress = record_note(
            progress,
            args.text,
            tags=args.tag,
            linked_task_id=args.task,
            linked_boss_id=args.boss,
            journey=journey,
        )
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _status_message(progress, journey, report_dir, prefix="已记录")

    if args.command == "complete-task":
        progress = complete_task(progress, args.task_id, journey)
        if args.note:
            progress = record_note(
                progress,
                args.note,
                linked_task_id=args.task_id,
                journey=journey,
            )
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _status_message(progress, journey, report_dir, prefix="已完成任务")

    if args.command == "complete-boss":
        progress = complete_boss(progress, args.boss_id, journey)
        if args.note:
            progress = record_note(
                progress,
                args.note,
                linked_boss_id=args.boss_id,
                journey=journey,
            )
        save_progress(progress, progress_path)
        save_reports(progress, journey, report_dir)
        return _status_message(progress, journey, report_dir, prefix="已通关 Boss")

    if args.command == "export":
        save_reports(progress, journey, report_dir)
        return _status_message(progress, journey, report_dir, prefix="已导出")

    raise ValueError(f"unknown command: {args.command}")


def main() -> None:
    print(run_command(_argv_without_program()))


def _argv_without_program() -> list[str]:
    import sys

    return sys.argv[1:]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="financial-report-rpg")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")

    note = subparsers.add_parser("note")
    note.add_argument("--text", required=True)
    note.add_argument("--tag", action="append", default=[])
    note.add_argument("--task")
    note.add_argument("--boss")

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
) -> str:
    summary = summarize_progress(progress, journey)
    report_path = Path(report_dir)
    return (
        f"{prefix}：{summary.level_title}，"
        f"{summary.xp}/{summary.max_xp} XP，"
        f"每日副本 {summary.daily_completed}/{summary.daily_total}，"
        f"Boss {summary.boss_completed}/{summary.boss_total}。"
        f"报告：{report_path / 'progress.md'}；{report_path / 'progress.html'}"
    )


if __name__ == "__main__":
    main()
