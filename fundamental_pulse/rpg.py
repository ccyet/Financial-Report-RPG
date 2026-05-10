from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RpgChapter:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class RpgTask:
    id: str
    title: str
    description: str
    xp: int


@dataclass(frozen=True)
class RpgBoss:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class RpgWorldRaid:
    title: str
    description: str
    unlock_required_bosses: int


@dataclass(frozen=True)
class RpgJourney:
    chapters: list[RpgChapter]
    daily_tasks: list[RpgTask]
    boss_tasks: list[RpgBoss]
    world_raid: RpgWorldRaid


@dataclass(frozen=True)
class RpgProgress:
    completed_tasks: set[str] = field(default_factory=set)
    completed_bosses: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class RpgProgressSummary:
    xp: int
    max_xp: int
    daily_completed: int
    daily_total: int
    boss_completed: int
    boss_total: int
    level_title: str
    level_description: str
    unlocked_badges: list[str]
    world_raid_unlocked: bool


def default_journey() -> RpgJourney:
    return RpgJourney(
        chapters=[
            RpgChapter(
                id="first_impression",
                title="初始印象",
                description="先写下对公司业务、客户和产业位置的第一判断，作为后续验证对象。",
            ),
            RpgChapter(
                id="revenue_structure",
                title="收入结构",
                description="拆产品、区域、客户和量价变化，找到增长来自哪里。",
            ),
            RpgChapter(
                id="profit_quality",
                title="利润质量",
                description="看毛利率、费用率、扣非利润和非经常性损益的真实贡献。",
            ),
            RpgChapter(
                id="cash_assets",
                title="现金与资产",
                description="用经营现金流、应收、存货和合同负债判断增长含金量。",
            ),
            RpgChapter(
                id="industry_compare",
                title="产业对比",
                description="放到同产业头部公司里比较，识别强弱、周期和分化。",
            ),
            RpgChapter(
                id="portrait_confirm",
                title="画像确认",
                description="回到第一印象，依据财报证据修正公司到底靠什么赚钱。",
            ),
            RpgChapter(
                id="idea_log",
                title="灵感沉淀",
                description="把结论、反证信号和后续跟踪动作写入个人研究日志。",
            ),
        ],
        daily_tasks=[
            RpgTask(
                id="mdna",
                title="读一页管理层讨论",
                description="只找管理层对收入、价格、需求、产能或客户结构的解释。",
                xp=20,
            ),
            RpgTask(
                id="profit",
                title="找一个利润变化原因",
                description="判断利润变化来自收入、毛利率、费用、减值还是非经常性项目。",
                xp=20,
            ),
            RpgTask(
                id="cash",
                title="核对现金流含金量",
                description="比较经营现金流与归母净利润，找是否存在利润好但现金弱。",
                xp=20,
            ),
            RpgTask(
                id="compare",
                title="对比一个产业同伴",
                description="把同产业另一家公司加入对照，观察收入增速、毛利率和库存差异。",
                xp=20,
            ),
            RpgTask(
                id="risk",
                title="记录一个反证信号",
                description="主动寻找可能推翻结论的信号：价格下行、应收走高、订单变弱。",
                xp=20,
            ),
            RpgTask(
                id="idea",
                title="沉淀一个投资灵感",
                description="把今天最值得跟踪的业务变化，归档成后续可复盘的研究线索。",
                xp=20,
            ),
        ],
        boss_tasks=[
            RpgBoss(
                id="three_year_map",
                title="三年财报地图",
                description="完成一家龙头公司三年收入、利润、现金流和资产负债地图。",
            ),
            RpgBoss(
                id="peer_battle",
                title="三家公司横向对战",
                description="完成同产业三家头部企业对比，说明谁在扩张、谁在承压。",
            ),
            RpgBoss(
                id="industry_log",
                title="产业灵感日志",
                description="沉淀一条产业变化线索，列出支持证据、反证信号和下次跟踪动作。",
            ),
            RpgBoss(
                id="portrait_review",
                title="画像复核报告",
                description="回到初始印象，说明哪些判断被证实、修正或推翻。",
            ),
        ],
        world_raid=RpgWorldRaid(
            title="世界副本：国家价值链坐标",
            description=(
                "完成 4 个 Boss 关卡后解锁。研究该产业在国家价值链中的位置："
                "基础能力、关键卡点、全球竞争优势，或下游应用扩散节点。"
            ),
            unlock_required_bosses=4,
        ),
    )


def summarize_progress(progress: RpgProgress, journey: RpgJourney) -> RpgProgressSummary:
    _validate_progress(progress, journey)
    daily_task_ids = {task.id for task in journey.daily_tasks}
    boss_ids = {boss.id for boss in journey.boss_tasks}
    daily_completed = len(progress.completed_tasks & daily_task_ids)
    boss_completed = len(progress.completed_bosses & boss_ids)
    xp = sum(task.xp for task in journey.daily_tasks if task.id in progress.completed_tasks)
    max_xp = sum(task.xp for task in journey.daily_tasks)
    level_title, level_description = _level_for(daily_completed)
    return RpgProgressSummary(
        xp=xp,
        max_xp=max_xp,
        daily_completed=daily_completed,
        daily_total=len(journey.daily_tasks),
        boss_completed=boss_completed,
        boss_total=len(journey.boss_tasks),
        level_title=level_title,
        level_description=level_description,
        unlocked_badges=_badges_for(daily_completed),
        world_raid_unlocked=boss_completed >= journey.world_raid.unlock_required_bosses,
    )


def toggle_task(progress: RpgProgress, task_id: str, journey: RpgJourney) -> RpgProgress:
    task_ids = {task.id for task in journey.daily_tasks}
    if task_id not in task_ids:
        raise ValueError(f"unknown RPG task id: {task_id}")
    completed = set(progress.completed_tasks)
    if task_id in completed:
        completed.remove(task_id)
    else:
        completed.add(task_id)
    return RpgProgress(
        completed_tasks=completed,
        completed_bosses=set(progress.completed_bosses),
    )


def toggle_boss(progress: RpgProgress, boss_id: str, journey: RpgJourney) -> RpgProgress:
    boss_ids = {boss.id for boss in journey.boss_tasks}
    if boss_id not in boss_ids:
        raise ValueError(f"unknown RPG boss id: {boss_id}")
    completed = set(progress.completed_bosses)
    if boss_id in completed:
        completed.remove(boss_id)
    else:
        completed.add(boss_id)
    return RpgProgress(
        completed_tasks=set(progress.completed_tasks),
        completed_bosses=completed,
    )


def load_progress(path: str | Path, journey: RpgJourney) -> RpgProgress:
    progress_path = Path(path)
    if not progress_path.exists():
        return RpgProgress()

    try:
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid RPG progress file: {progress_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"invalid RPG progress file: {progress_path}")
    progress = RpgProgress(
        completed_tasks=_string_set(payload.get("completed_tasks"), "completed_tasks"),
        completed_bosses=_string_set(payload.get("completed_bosses"), "completed_bosses"),
    )
    _validate_progress(progress, journey)
    return progress


def save_progress(progress: RpgProgress, path: str | Path) -> None:
    progress_path = Path(path)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "completed_tasks": sorted(progress.completed_tasks),
        "completed_bosses": sorted(progress.completed_bosses),
    }
    progress_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_progress(progress: RpgProgress, journey: RpgJourney) -> None:
    task_ids = {task.id for task in journey.daily_tasks}
    boss_ids = {boss.id for boss in journey.boss_tasks}
    unknown_tasks = progress.completed_tasks - task_ids
    unknown_bosses = progress.completed_bosses - boss_ids
    if unknown_tasks:
        raise ValueError(f"unknown RPG task id: {sorted(unknown_tasks)[0]}")
    if unknown_bosses:
        raise ValueError(f"unknown RPG boss id: {sorted(unknown_bosses)[0]}")


def _string_set(value: Any, field_name: str) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"invalid RPG progress field: {field_name}")
    return set(value)


def _level_for(completed_count: int) -> tuple[str, str]:
    if completed_count >= 6:
        return "Lv.4 产业副本通关者", "全部每日副本已完成，可以挑战 Boss 关卡。"
    if completed_count >= 4:
        return "Lv.3 产业链探索者", "已经能把单家公司放进产业场景里比较。"
    if completed_count >= 2:
        return "Lv.2 指标观察员", "开始从收入、利润和现金流里找线索。"
    return "Lv.1 财报新兵", "完成每日副本，解锁研究徽章。"


def _badges_for(completed_count: int) -> list[str]:
    badges = []
    if completed_count >= 1:
        badges.append("首日开荒")
    if completed_count >= 3:
        badges.append("指标猎手")
    if completed_count >= 5:
        badges.append("产业行者")
    if completed_count >= 6:
        badges.append("副本通关")
    return badges
