from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_LEVEL = 175
MAIN_CHAPTER_CAP = 50
BOSS_CAP = 99


@dataclass(frozen=True)
class RpgChapter:
    id: str
    title: str
    description: str
    check_in_prompt: str
    pass_criteria: list[str]


@dataclass(frozen=True)
class RpgTask:
    id: str
    title: str
    description: str
    xp: int
    check_in_prompt: str
    pass_criteria: list[str]


@dataclass(frozen=True)
class RpgBoss:
    id: str
    title: str
    description: str
    pass_criteria: list[str]


@dataclass(frozen=True)
class RpgWorldRaid:
    title: str
    description: str
    unlock_required_bosses: int
    check_in_prompt: str
    pass_criteria: list[str]


@dataclass(frozen=True)
class RpgJourney:
    chapters: list[RpgChapter]
    daily_tasks: list[RpgTask]
    boss_tasks: list[RpgBoss]
    world_raid: RpgWorldRaid


@dataclass(frozen=True)
class RpgNote:
    id: str
    created_at: str
    text: str
    tags: list[str] = field(default_factory=list)
    linked_chapter_id: str | None = None
    linked_task_id: str | None = None
    linked_boss_id: str | None = None


@dataclass(frozen=True)
class RpgProgress:
    active_dungeon: str | None = None
    completed_chapters: set[str] = field(default_factory=set)
    completed_tasks: set[str] = field(default_factory=set)
    completed_bosses: set[str] = field(default_factory=set)
    notes: list[RpgNote] = field(default_factory=list)
    dungeons: dict[str, RpgProgress] = field(default_factory=dict)

    def switch_dungeon(self, dungeon: str) -> RpgProgress:
        name = dungeon.strip()
        if not name:
            raise ValueError("RPG dungeon name cannot be empty")
        current = self._with_active_snapshot()
        if name not in current.dungeons:
            current = current.with_dungeon(name, RpgProgress(active_dungeon=name))
        return RpgProgress(
            active_dungeon=name,
            dungeons=dict(current.dungeons),
        )

    def with_dungeon(self, dungeon: str, progress: RpgProgress) -> RpgProgress:
        name = dungeon.strip()
        if not name:
            raise ValueError("RPG dungeon name cannot be empty")
        snapshot = progress.as_dungeon_snapshot(name)
        dungeons = dict(self.dungeons)
        dungeons[name] = snapshot
        return RpgProgress(
            active_dungeon=self.active_dungeon or name,
            dungeons=dungeons,
        )

    def as_dungeon_snapshot(self, dungeon: str | None = None) -> RpgProgress:
        return RpgProgress(
            active_dungeon=dungeon or self.active_dungeon,
            completed_chapters=set(self.completed_chapters),
            completed_tasks=set(self.completed_tasks),
            completed_bosses=set(self.completed_bosses),
            notes=list(self.notes),
        )

    def _with_active_snapshot(self) -> RpgProgress:
        if not self.active_dungeon:
            return self
        active = self.as_dungeon_snapshot(self.active_dungeon)
        if _is_empty_dungeon_snapshot(active):
            return self
        dungeons = dict(self.dungeons)
        dungeons[self.active_dungeon] = active
        return RpgProgress(active_dungeon=self.active_dungeon, dungeons=dungeons)


@dataclass(frozen=True)
class RpgProgressSummary:
    level: int
    max_level: int
    xp: int
    max_xp: int
    chapter_completed: int
    chapter_total: int
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
                check_in_prompt="先说出你对这家公司业务、客户、产业位置的第一判断。",
                pass_criteria=[
                    "能说清公司大致卖什么、卖给谁。",
                    "能判断它在产业链上游、中游、下游或平台环节的位置。",
                    "明确这只是第一印象，至少留下 1 个待验证问题。",
                ],
            ),
            RpgChapter(
                id="revenue_structure",
                title="收入结构",
                description="拆产品、区域、客户和量价变化，找到增长来自哪里。",
                check_in_prompt="把收入拆成产品、区域、客户或量价中的至少两个维度。",
                pass_criteria=[
                    "指出主要收入来源，不只说总收入涨跌。",
                    "区分增长来自销量、价格、产品结构、区域或客户变化。",
                    "留下 1 条需要回到财报附注或管理层讨论验证的线索。",
                ],
            ),
            RpgChapter(
                id="profit_quality",
                title="利润质量",
                description="看毛利率、费用率、扣非利润和非经常性损益的真实贡献。",
                check_in_prompt="说明利润变化到底来自经营改善还是一次性项目。",
                pass_criteria=[
                    "至少检查毛利率、费用率、扣非利润中的两个指标。",
                    "识别是否存在非经常性损益、减值或补贴影响。",
                    "能写出 1 句对利润质量的暂定判断。",
                ],
            ),
            RpgChapter(
                id="cash_assets",
                title="现金与资产",
                description="用经营现金流、应收、存货和合同负债判断增长含金量。",
                check_in_prompt="用现金流和资产项目验证增长是否有含金量。",
                pass_criteria=[
                    "比较经营现金流和净利润方向是否一致。",
                    "至少查看应收、存货、合同负债中的两个项目。",
                    "写出 1 个现金强或现金弱的原因假设。",
                ],
            ),
            RpgChapter(
                id="industry_compare",
                title="产业对比",
                description="放到同产业头部公司里比较，识别强弱、周期和分化。",
                check_in_prompt="找一个同产业对照公司，说明两家公司差异在哪里。",
                pass_criteria=[
                    "至少选择 1 家同产业头部公司作为参照。",
                    "比较收入增速、毛利率、现金流或库存中的两个维度。",
                    "写出公司强弱来自自身能力还是行业周期的判断。",
                ],
            ),
            RpgChapter(
                id="portrait_confirm",
                title="画像确认",
                description="回到第一印象，依据财报证据修正公司到底靠什么赚钱。",
                check_in_prompt="回到第一印象，说明哪些判断被证实、修正或推翻。",
                pass_criteria=[
                    "引用前面至少 2 条财报证据修正公司画像。",
                    "说清公司真正靠什么赚钱，而不是只复述业务介绍。",
                    "保留 1 条尚未解决的反证或跟踪问题。",
                ],
            ),
            RpgChapter(
                id="idea_log",
                title="灵感沉淀",
                description="把结论、反证信号和后续跟踪动作写入个人研究日志。",
                check_in_prompt="把本轮阅读沉淀成可复盘的研究灵感和下一步动作。",
                pass_criteria=[
                    "形成 1 条可复盘的产业或公司变化线索。",
                    "同时记录支持证据和可能推翻它的反证信号。",
                    "明确下一次要跟踪的财报项目、公司或产业事件。",
                ],
            ),
        ],
        daily_tasks=[
            RpgTask(
                id="mdna",
                title="读一页管理层讨论",
                description="只找管理层对收入、价格、需求、产能或客户结构的解释。",
                xp=20,
                check_in_prompt="今天从管理层讨论里摘出一个经营变化解释。",
                pass_criteria=[
                    "说出变化发生在收入、价格、需求、产能或客户结构中的哪一类。",
                    "保留管理层解释和自己的验证问题。",
                    "完成后可打卡。",
                ],
            ),
            RpgTask(
                id="profit",
                title="找一个利润变化原因",
                description="判断利润变化来自收入、毛利率、费用、减值还是非经常性项目。",
                xp=20,
                check_in_prompt="今天只找一个利润变化原因，不扩展成完整报告。",
                pass_criteria=[
                    "明确利润变化来自收入、毛利率、费用、减值或非经常性项目中的哪一类。",
                    "写出它是经营性变化还是一次性变化。",
                    "完成后可打卡。",
                ],
            ),
            RpgTask(
                id="cash",
                title="核对现金流含金量",
                description="比较经营现金流与归母净利润，找是否存在利润好但现金弱。",
                xp=20,
                check_in_prompt="今天只核对经营现金流和利润是否匹配。",
                pass_criteria=[
                    "比较经营现金流和归母净利润的方向或比例。",
                    "指出现金流强弱可能来自回款、库存、预收或资本开支中的哪一类。",
                    "完成后可打卡。",
                ],
            ),
            RpgTask(
                id="compare",
                title="对比一个产业同伴",
                description="把同产业另一家公司加入对照，观察收入增速、毛利率和库存差异。",
                xp=20,
                check_in_prompt="今天只加入一个同产业对照公司。",
                pass_criteria=[
                    "选出 1 家对照公司并说明为什么可比。",
                    "至少比较收入增速、毛利率、库存或现金流中的一个指标。",
                    "完成后可打卡。",
                ],
            ),
            RpgTask(
                id="risk",
                title="记录一个反证信号",
                description="主动寻找可能推翻结论的信号：价格下行、应收走高、订单变弱。",
                xp=20,
                check_in_prompt="今天只记录一个可能推翻当前判断的信号。",
                pass_criteria=[
                    "反证信号要具体到价格、应收、订单、库存、竞争或政策中的一类。",
                    "说明它会推翻哪一个原判断。",
                    "完成后可打卡。",
                ],
            ),
            RpgTask(
                id="idea",
                title="沉淀一个投资灵感",
                description="把今天最值得跟踪的业务变化，归档成后续可复盘的研究线索。",
                xp=20,
                check_in_prompt="今天只沉淀一个值得后续跟踪的研究灵感。",
                pass_criteria=[
                    "灵感必须来自财报里的一个变化，而不是泛泛观点。",
                    "同时写出下一次要验证的数据或事件。",
                    "完成后可打卡。",
                ],
            ),
        ],
        boss_tasks=[
            RpgBoss(
                id="three_year_map",
                title="三年财报地图",
                description="完成一家龙头公司三年收入、利润、现金流和资产负债地图。",
                pass_criteria=[
                    "覆盖同一家公司连续三年的收入、利润、现金流和资产负债。",
                    "写出三年里最关键的一条变化主线。",
                    "能指出至少 1 个后续跟踪变量。",
                ],
            ),
            RpgBoss(
                id="peer_battle",
                title="三家公司横向对战",
                description="完成同产业三家头部企业对比，说明谁在扩张、谁在承压。",
                pass_criteria=[
                    "至少包含三家同产业公司。",
                    "用两个以上指标说明谁在扩张、谁在承压。",
                    "给出产业分化背后的原因假设。",
                ],
            ),
            RpgBoss(
                id="industry_log",
                title="产业灵感日志",
                description="沉淀一条产业变化线索，列出支持证据、反证信号和下次跟踪动作。",
                pass_criteria=[
                    "形成一条产业变化线索。",
                    "同时列出支持证据和反证信号。",
                    "明确下次跟踪动作。",
                ],
            ),
            RpgBoss(
                id="portrait_review",
                title="画像复核报告",
                description="回到初始印象，说明哪些判断被证实、修正或推翻。",
                pass_criteria=[
                    "逐条回看初始印象。",
                    "说明哪些判断被证实、修正或推翻。",
                    "形成新版公司画像。",
                ],
            ),
        ],
        world_raid=RpgWorldRaid(
            title="世界副本：国家价值链坐标",
            description=(
                "完成 4 个 Boss 关卡后解锁。研究该产业在国家价值链中的位置："
                "基础能力、关键卡点、全球竞争优势，或下游应用扩散节点。"
            ),
            unlock_required_bosses=4,
            check_in_prompt="研究该产业在国家价值链中的位置。",
            pass_criteria=[
                "说明产业承担的是基础能力、关键卡点、全球竞争优势还是下游扩散节点。",
                "至少引用 2 条企业或产业层面的证据。",
                "写出国产替代、全球竞争或国家价值链位置的一条判断。",
            ],
        ),
    )


def summarize_progress(progress: RpgProgress, journey: RpgJourney) -> RpgProgressSummary:
    progress = dungeon_progress(progress)
    _validate_progress(progress, journey)
    daily_task_ids = {task.id for task in journey.daily_tasks}
    chapter_ids = {chapter.id for chapter in journey.chapters}
    boss_ids = {boss.id for boss in journey.boss_tasks}
    chapter_completed = len(progress.completed_chapters & chapter_ids)
    daily_completed = len(progress.completed_tasks & daily_task_ids)
    boss_completed = len(progress.completed_bosses & boss_ids)
    xp = sum(task.xp for task in journey.daily_tasks if task.id in progress.completed_tasks)
    max_xp = sum(task.xp for task in journey.daily_tasks)
    level = min(MAX_LEVEL, 1 + chapter_completed + daily_completed)
    level_title, level_description = _level_for(daily_completed)
    return RpgProgressSummary(
        level=level,
        max_level=MAX_LEVEL,
        xp=xp,
        max_xp=max_xp,
        chapter_completed=chapter_completed,
        chapter_total=MAIN_CHAPTER_CAP,
        daily_completed=daily_completed,
        daily_total=len(journey.daily_tasks),
        boss_completed=boss_completed,
        boss_total=BOSS_CAP,
        level_title=level_title,
        level_description=level_description,
        unlocked_badges=_badges_for(daily_completed),
        world_raid_unlocked=boss_completed >= journey.world_raid.unlock_required_bosses,
    )


def toggle_task(progress: RpgProgress, task_id: str, journey: RpgJourney) -> RpgProgress:
    progress = dungeon_progress(progress)
    task_ids = {task.id for task in journey.daily_tasks}
    if task_id not in task_ids:
        raise ValueError(f"unknown RPG task id: {task_id}")
    completed = set(progress.completed_tasks)
    if task_id in completed:
        completed.remove(task_id)
    else:
        completed.add(task_id)
    return RpgProgress(
        active_dungeon=progress.active_dungeon,
        completed_chapters=set(progress.completed_chapters),
        completed_tasks=completed,
        completed_bosses=set(progress.completed_bosses),
        notes=list(progress.notes),
    )


def toggle_boss(progress: RpgProgress, boss_id: str, journey: RpgJourney) -> RpgProgress:
    progress = dungeon_progress(progress)
    boss_ids = {boss.id for boss in journey.boss_tasks}
    if boss_id not in boss_ids:
        raise ValueError(f"unknown RPG boss id: {boss_id}")
    completed = set(progress.completed_bosses)
    if boss_id in completed:
        completed.remove(boss_id)
    else:
        completed.add(boss_id)
    return RpgProgress(
        active_dungeon=progress.active_dungeon,
        completed_chapters=set(progress.completed_chapters),
        completed_tasks=set(progress.completed_tasks),
        completed_bosses=completed,
        notes=list(progress.notes),
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
    dungeons = _dungeons_from_payload(payload.get("dungeons"), journey)
    progress = RpgProgress(
        active_dungeon=_optional_string(payload.get("active_dungeon"), "active_dungeon"),
        completed_chapters=_string_set(payload.get("completed_chapters"), "completed_chapters"),
        completed_tasks=_string_set(payload.get("completed_tasks"), "completed_tasks"),
        completed_bosses=_string_set(payload.get("completed_bosses"), "completed_bosses"),
        notes=_notes_from_payload(payload.get("notes")),
        dungeons=dungeons,
    )
    if progress.active_dungeon and progress.active_dungeon not in progress.dungeons:
        progress = progress.with_dungeon(progress.active_dungeon, progress)
    _validate_progress(progress, journey)
    return progress


def save_progress(progress: RpgProgress, path: str | Path) -> None:
    progress_path = Path(path)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "active_dungeon": progress.active_dungeon,
        "completed_tasks": sorted(progress.completed_tasks),
        "completed_chapters": sorted(progress.completed_chapters),
        "completed_bosses": sorted(progress.completed_bosses),
        "notes": [
            {
                "id": note.id,
                "created_at": note.created_at,
                "text": note.text,
                "tags": note.tags,
                "linked_chapter_id": note.linked_chapter_id,
                "linked_task_id": note.linked_task_id,
                "linked_boss_id": note.linked_boss_id,
            }
            for note in progress.notes
        ],
        "dungeons": {
            name: _progress_payload(dungeon_progress(snapshot, name))
            for name, snapshot in sorted(progress._with_active_snapshot().dungeons.items())
        },
    }
    progress_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_progress(progress: RpgProgress, journey: RpgJourney) -> None:
    progress = dungeon_progress(progress)
    task_ids = {task.id for task in journey.daily_tasks}
    chapter_ids = {chapter.id for chapter in journey.chapters}
    boss_ids = {boss.id for boss in journey.boss_tasks}
    unknown_chapters = progress.completed_chapters - chapter_ids
    unknown_tasks = progress.completed_tasks - task_ids
    unknown_bosses = progress.completed_bosses - boss_ids
    if unknown_chapters:
        raise ValueError(f"unknown RPG chapter id: {sorted(unknown_chapters)[0]}")
    if unknown_tasks:
        raise ValueError(f"unknown RPG task id: {sorted(unknown_tasks)[0]}")
    if unknown_bosses:
        raise ValueError(f"unknown RPG boss id: {sorted(unknown_bosses)[0]}")
    for note in progress.notes:
        if note.linked_chapter_id is not None and note.linked_chapter_id not in chapter_ids:
            raise ValueError(f"unknown RPG chapter id: {note.linked_chapter_id}")
        if note.linked_task_id is not None and note.linked_task_id not in task_ids:
            raise ValueError(f"unknown RPG task id: {note.linked_task_id}")
        if note.linked_boss_id is not None and note.linked_boss_id not in boss_ids:
            raise ValueError(f"unknown RPG boss id: {note.linked_boss_id}")


def dungeon_progress(progress: RpgProgress, dungeon: str | None = None) -> RpgProgress:
    name = dungeon or progress.active_dungeon
    if not name:
        return progress.as_dungeon_snapshot(None)
    if name in progress.dungeons:
        return progress.dungeons[name].as_dungeon_snapshot(name)
    if name == progress.active_dungeon:
        return progress.as_dungeon_snapshot(name)
    return RpgProgress(active_dungeon=name)


def _progress_payload(progress: RpgProgress) -> dict[str, Any]:
    return {
        "completed_tasks": sorted(progress.completed_tasks),
        "completed_chapters": sorted(progress.completed_chapters),
        "completed_bosses": sorted(progress.completed_bosses),
        "notes": [
            {
                "id": note.id,
                "created_at": note.created_at,
                "text": note.text,
                "tags": note.tags,
                "linked_chapter_id": note.linked_chapter_id,
                "linked_task_id": note.linked_task_id,
                "linked_boss_id": note.linked_boss_id,
            }
            for note in progress.notes
        ],
    }


def _dungeons_from_payload(value: Any, journey: RpgJourney) -> dict[str, RpgProgress]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("invalid RPG progress field: dungeons")
    dungeons = {}
    for name, payload in value.items():
        if not isinstance(name, str) or not isinstance(payload, dict):
            raise ValueError("invalid RPG progress field: dungeons")
        snapshot = RpgProgress(
            active_dungeon=name,
            completed_chapters=_string_set(
                payload.get("completed_chapters"), "dungeons.completed_chapters"
            ),
            completed_tasks=_string_set(payload.get("completed_tasks"), "dungeons.completed_tasks"),
            completed_bosses=_string_set(
                payload.get("completed_bosses"), "dungeons.completed_bosses"
            ),
            notes=_notes_from_payload(payload.get("notes")),
        )
        _validate_progress(snapshot, journey)
        dungeons[name] = snapshot
    return dungeons


def _is_empty_dungeon_snapshot(progress: RpgProgress) -> bool:
    return not (
        progress.completed_chapters
        or progress.completed_tasks
        or progress.completed_bosses
        or progress.notes
    )


def _string_set(value: Any, field_name: str) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"invalid RPG progress field: {field_name}")
    return set(value)


def _string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"invalid RPG progress field: {field_name}")
    return list(value)


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid RPG progress field: {field_name}")
    return value


def _notes_from_payload(value: Any) -> list[RpgNote]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("invalid RPG progress field: notes")

    notes = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("invalid RPG progress field: notes")
        note_id = item.get("id")
        created_at = item.get("created_at")
        text = item.get("text")
        if (
            not isinstance(note_id, str)
            or not isinstance(created_at, str)
            or not isinstance(text, str)
        ):
            raise ValueError("invalid RPG progress field: notes")
        notes.append(
            RpgNote(
                id=note_id,
                created_at=created_at,
                text=text,
                tags=_string_list(item.get("tags"), "notes.tags"),
                linked_chapter_id=_optional_string(
                    item.get("linked_chapter_id"), "notes.linked_chapter_id"
                ),
                linked_task_id=_optional_string(item.get("linked_task_id"), "notes.linked_task_id"),
                linked_boss_id=_optional_string(item.get("linked_boss_id"), "notes.linked_boss_id"),
            )
        )
    return notes


def _level_for(completed_count: int) -> tuple[str, str]:
    if completed_count >= 6:
        return "产业副本通关者", "全部每日副本已完成，可以挑战 Boss 关卡。"
    if completed_count >= 4:
        return "产业链探索者", "已经能把单家公司放进产业场景里比较。"
    if completed_count >= 2:
        return "指标观察员", "开始从收入、利润和现金流里找线索。"
    return "财报新兵", "完成每日副本，解锁研究徽章。"


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
