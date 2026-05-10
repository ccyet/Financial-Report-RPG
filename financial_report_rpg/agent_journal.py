from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from financial_report_rpg.rpg import (
    RpgJourney,
    RpgNote,
    RpgProgress,
    dungeon_progress,
    summarize_progress,
)

DEFAULT_REPORT_DIR = Path(".local/rpg_exports")
TEXT_REPORT_NAME = "progress.md"
HTML_REPORT_NAME = "progress.html"


@dataclass(frozen=True)
class GuidedCheckIn:
    kind: str
    id: str
    title: str
    prompt: str
    pass_criteria: list[str]
    completion_command: str


def record_note(
    progress: RpgProgress,
    text: str,
    *,
    journey: RpgJourney,
    tags: list[str] | None = None,
    linked_chapter_id: str | None = None,
    linked_task_id: str | None = None,
    linked_boss_id: str | None = None,
    created_at: str | None = None,
) -> RpgProgress:
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("RPG note text cannot be empty")

    note_created_at = created_at or datetime.now(UTC).isoformat()
    note = RpgNote(
        id=_note_id(normalized_text, note_created_at),
        created_at=note_created_at,
        text=normalized_text,
        tags=list(tags or []),
        linked_chapter_id=linked_chapter_id,
        linked_task_id=linked_task_id,
        linked_boss_id=linked_boss_id,
    )
    updated = replace(progress, notes=[*progress.notes, note])
    summarize_progress(updated, journey)
    return updated


def complete_chapter(progress: RpgProgress, chapter_id: str, journey: RpgJourney) -> RpgProgress:
    updated = replace(progress, completed_chapters={*progress.completed_chapters, chapter_id})
    summarize_progress(updated, journey)
    return updated


def complete_task(progress: RpgProgress, task_id: str, journey: RpgJourney) -> RpgProgress:
    updated = replace(progress, completed_tasks={*progress.completed_tasks, task_id})
    summarize_progress(updated, journey)
    return updated


def next_check_in(progress: RpgProgress, journey: RpgJourney) -> GuidedCheckIn:
    progress = dungeon_progress(progress)
    summarize_progress(progress, journey)
    for chapter in journey.chapters:
        if chapter.id not in progress.completed_chapters:
            return GuidedCheckIn(
                kind="chapter",
                id=chapter.id,
                title=chapter.title,
                prompt=chapter.check_in_prompt,
                pass_criteria=chapter.pass_criteria,
                completion_command=f"complete-chapter {chapter.id}",
            )
    for task in journey.daily_tasks:
        if task.id not in progress.completed_tasks:
            return GuidedCheckIn(
                kind="daily_task",
                id=task.id,
                title=task.title,
                prompt=task.check_in_prompt,
                pass_criteria=task.pass_criteria,
                completion_command=f"complete-task {task.id}",
            )
    for boss in journey.boss_tasks:
        if boss.id not in progress.completed_bosses:
            return GuidedCheckIn(
                kind="boss",
                id=boss.id,
                title=boss.title,
                prompt=boss.description,
                pass_criteria=boss.pass_criteria,
                completion_command=f"complete-boss {boss.id}",
            )
    return GuidedCheckIn(
        kind="world_raid",
        id="world_raid",
        title=journey.world_raid.title,
        prompt=journey.world_raid.check_in_prompt,
        pass_criteria=journey.world_raid.pass_criteria,
        completion_command="export",
    )


def complete_boss(progress: RpgProgress, boss_id: str, journey: RpgJourney) -> RpgProgress:
    updated = replace(progress, completed_bosses={*progress.completed_bosses, boss_id})
    summarize_progress(updated, journey)
    return updated


def generate_text_report(progress: RpgProgress, journey: RpgJourney) -> str:
    progress = dungeon_progress(progress)
    summary = summarize_progress(progress, journey)
    level_label = _level_label(summary)
    dungeon_label = progress.active_dungeon or "未选择行业副本"
    badges = "、".join(summary.unlocked_badges) if summary.unlocked_badges else "暂无"
    completed_tasks = _completed_task_lines(progress, journey)
    completed_chapters = _completed_chapter_lines(progress, journey)
    completed_bosses = _completed_boss_lines(progress, journey)
    notes = _note_lines(progress)
    world_raid_status = "已解锁" if summary.world_raid_unlocked else "未解锁"
    gate = next_check_in(progress, journey)

    return "\n".join(
        [
            "# 财报 RPG 当前进度",
            "",
            f"- 当前副本：{dungeon_label}",
            f"- 等级：{level_label}",
            f"- 经验：{summary.xp}/{summary.max_xp} XP",
            f"- 主线关卡：{summary.chapter_completed}/{summary.chapter_total}",
            f"- 每日副本：{summary.daily_completed}/{summary.daily_total}",
            f"- Boss 关卡：{summary.boss_completed}/{summary.boss_total}",
            f"- 已解锁徽章：{badges}",
            f"- 世界副本：{world_raid_status}，{journey.world_raid.title}",
            "",
            "## 当前关卡",
            f"- {gate.title}：{gate.prompt}",
            "- 通关标准：",
            *[f"  - {criterion}" for criterion in gate.pass_criteria],
            f"- 打卡命令：{gate.completion_command}",
            "",
            "## 已完成主线关卡",
            *(completed_chapters or ["- 暂无"]),
            "",
            "## 已完成每日副本",
            *(completed_tasks or ["- 暂无"]),
            "",
            "## 已完成 Boss 关卡",
            *(completed_bosses or ["- 暂无"]),
            "",
            "## 对话记录与研究想法",
            *(notes or ["- 暂无"]),
            "",
            "## 下一步",
            f"- {summary.level_description}",
            "- 本记录用于财报阅读训练和研究过程整理，不构成投资建议。",
            "",
        ]
    )


def generate_html_report(progress: RpgProgress, journey: RpgJourney) -> str:
    progress = dungeon_progress(progress)
    summary = summarize_progress(progress, journey)
    level_label = _level_label(summary)
    dungeon_label = progress.active_dungeon or "未选择行业副本"
    badges = summary.unlocked_badges or ["暂无"]
    world_raid_status = "已解锁" if summary.world_raid_unlocked else "未解锁"
    chapter_metric = f"{summary.chapter_completed}/{summary.chapter_total}"
    daily_metric = f"{summary.daily_completed}/{summary.daily_total}"
    boss_metric = f"{summary.boss_completed}/{summary.boss_total}"
    gate = next_check_in(progress, journey)

    chapter_cards = _html_cards(_completed_chapter_lines(progress, journey) or ["暂无完成主线"])
    task_cards = _html_cards(_completed_task_lines(progress, journey) or ["暂无完成副本"])
    boss_cards = _html_cards(_completed_boss_lines(progress, journey) or ["暂无通关 Boss"])
    note_cards = _html_cards(_note_lines(progress) or ["暂无对话记录"])
    badge_nodes = "".join(f"<span>{escape(badge)}</span>" for badge in badges)
    criteria_nodes = "".join(f"<li>{escape(criterion)}</li>" for criterion in gate.pass_criteria)
    progress_bars = "".join(
        [
            _progress_bar("等级", summary.level, summary.max_level),
            _progress_bar("主线", summary.chapter_completed, summary.chapter_total),
            _progress_bar("Boss", summary.boss_completed, summary.boss_total),
        ]
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>财报 RPG 当前进度</title>
  <style>
    body {{
      margin: 0;
      color: #101827;
      background: #111827;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px;
    }}
    section {{
      margin: 18px 0;
      padding: 18px;
      background: #fff7e8;
      border: 3px solid #1f2937;
      box-shadow: 6px 6px 0 #000;
    }}
    h1, h2 {{
      margin: 0 0 12px;
      line-height: 1.2;
    }}
    .status {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
    }}
    .metric, .card {{
      padding: 12px;
      background: #e5eefb;
      border: 2px solid #1f2937;
    }}
    .metric strong {{
      display: block;
      margin-top: 6px;
      font-size: 20px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .badges span {{
      display: inline-block;
      margin: 0 8px 8px 0;
      padding: 5px 8px;
      background: #ffd166;
      border: 2px solid #1f2937;
      font-weight: 700;
    }}
    .bar {{
      margin: 12px 0;
    }}
    .bar-label {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
      font-weight: 700;
    }}
    .bar-track {{
      height: 16px;
      background: #fef3c7;
      border: 2px solid #1f2937;
    }}
    .bar-fill {{
      height: 100%;
      background: #38bdf8;
    }}
    footer {{
      color: #f9fafb;
      opacity: .85;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <section>
      <h1>财报 RPG 当前进度</h1>
      <div class="status">
        <div class="metric">当前副本<strong>{escape(dungeon_label)}</strong></div>
        <div class="metric">等级<strong>{escape(level_label)}</strong></div>
        <div class="metric">经验<strong>{summary.xp}/{summary.max_xp} XP</strong></div>
        <div class="metric">主线关卡<strong>{chapter_metric}</strong></div>
        <div class="metric">每日副本<strong>{daily_metric}</strong></div>
        <div class="metric">Boss 关卡<strong>{boss_metric}</strong></div>
      </div>
      {progress_bars}
    </section>
    <section>
      <h2>当前关卡</h2>
      <p><strong>{escape(gate.title)}</strong>：{escape(gate.prompt)}</p>
      <h3>通关标准</h3>
      <ul>{criteria_nodes}</ul>
      <p>打卡命令：{escape(gate.completion_command)}</p>
    </section>
    <section>
      <h2>徽章与世界副本</h2>
      <p>世界副本：{escape(world_raid_status)}，{escape(journey.world_raid.title)}</p>
      <div class="badges">{badge_nodes}</div>
    </section>
    <section>
      <h2>已完成主线关卡</h2>
      <div class="cards">{chapter_cards}</div>
    </section>
    <section>
      <h2>已完成每日副本</h2>
      <div class="cards">{task_cards}</div>
    </section>
    <section>
      <h2>已完成 Boss 关卡</h2>
      <div class="cards">{boss_cards}</div>
    </section>
    <section>
      <h2>对话记录与研究想法</h2>
      <div class="cards">{note_cards}</div>
    </section>
    <footer>本记录用于财报阅读训练和研究过程整理，不构成投资建议。</footer>
  </main>
</body>
</html>
"""


def save_reports(
    progress: RpgProgress,
    journey: RpgJourney,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    text_path = report_dir / TEXT_REPORT_NAME
    html_path = report_dir / HTML_REPORT_NAME
    text_path.write_text(generate_text_report(progress, journey), encoding="utf-8")
    html_path.write_text(generate_html_report(progress, journey), encoding="utf-8")
    return text_path, html_path


def build_notion_export(progress: RpgProgress, journey: RpgJourney) -> dict[str, Any]:
    progress = dungeon_progress(progress)
    summary = summarize_progress(progress, journey)
    return {
        "title": "财报 RPG 当前进度",
        "properties": {
            "level": _level_label(summary),
            "xp": summary.xp,
            "chapter_completed": summary.chapter_completed,
            "daily_completed": summary.daily_completed,
            "boss_completed": summary.boss_completed,
            "world_raid_unlocked": summary.world_raid_unlocked,
        },
        "markdown": generate_text_report(progress, journey),
    }


def _level_label(summary) -> str:
    return f"Lv.{summary.level}/{summary.max_level} {summary.level_title}"


def _progress_bar(label: str, current: int, total: int) -> str:
    ratio = 0 if total <= 0 else min(100, round(current / total * 100, 2))
    return (
        '<div class="bar">'
        f'<div class="bar-label"><span>{escape(label)}</span><span>{current}/{total}</span></div>'
        '<div class="bar-track">'
        f'<div class="bar-fill" style="width: {ratio}%"></div>'
        "</div></div>"
    )


def _note_id(text: str, created_at: str) -> str:
    raw = f"{created_at}\n{text}".encode()
    return hashlib.sha1(raw).hexdigest()[:12]


def _completed_task_lines(progress: RpgProgress, journey: RpgJourney) -> list[str]:
    return [
        f"- {task.title}：{task.description}"
        for task in journey.daily_tasks
        if task.id in progress.completed_tasks
    ]


def _completed_chapter_lines(progress: RpgProgress, journey: RpgJourney) -> list[str]:
    return [
        f"- {chapter.title}：{chapter.description}"
        for chapter in journey.chapters
        if chapter.id in progress.completed_chapters
    ]


def _completed_boss_lines(progress: RpgProgress, journey: RpgJourney) -> list[str]:
    return [
        f"- {boss.title}：{boss.description}"
        for boss in journey.boss_tasks
        if boss.id in progress.completed_bosses
    ]


def _note_lines(progress: RpgProgress) -> list[str]:
    lines = []
    for note in progress.notes:
        tags = f" #{' #'.join(note.tags)}" if note.tags else ""
        links = []
        if note.linked_task_id:
            links.append(f"任务 {note.linked_task_id}")
        if note.linked_chapter_id:
            links.append(f"主线 {note.linked_chapter_id}")
        if note.linked_boss_id:
            links.append(f"Boss {note.linked_boss_id}")
        suffix = f"（{', '.join(links)}）" if links else ""
        lines.append(f"- {note.created_at}：{note.text}{tags}{suffix}")
    return lines


def _html_cards(lines: list[str]) -> str:
    cards = []
    for line in lines:
        normalized = line[2:] if line.startswith("- ") else line
        cards.append(f'<div class="card">{escape(normalized)}</div>')
    return "".join(cards)
