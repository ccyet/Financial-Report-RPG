from pathlib import Path

import pytest

from fundamental_pulse.rpg import (
    RpgProgress,
    default_journey,
    load_progress,
    save_progress,
    summarize_progress,
    toggle_boss,
    toggle_task,
)


def test_default_rpg_journey_has_delivery_milestones():
    journey = default_journey()

    assert len(journey.chapters) == 7
    assert journey.chapters[0].title == "初始印象"
    assert journey.chapters[-2].title == "画像确认"
    assert len(journey.daily_tasks) == 6
    assert len(journey.boss_tasks) == 4
    assert journey.world_raid.unlock_required_bosses == 4


def test_task_progress_updates_level_badges_and_world_raid_separately():
    journey = default_journey()
    progress = RpgProgress()

    for task in journey.daily_tasks[:3]:
        progress = toggle_task(progress, task.id, journey)
    summary = summarize_progress(progress, journey)

    assert summary.daily_completed == 3
    assert summary.xp == 60
    assert summary.level_title == "Lv.2 指标观察员"
    assert summary.unlocked_badges == ["首日开荒", "指标猎手"]
    assert summary.world_raid_unlocked is False

    for boss in journey.boss_tasks:
        progress = toggle_boss(progress, boss.id, journey)
    summary = summarize_progress(progress, journey)

    assert summary.boss_completed == 4
    assert summary.world_raid_unlocked is True


def test_progress_persists_to_json(tmp_path: Path):
    journey = default_journey()
    path = tmp_path / "progress.json"
    progress = toggle_boss(toggle_task(RpgProgress(), "mdna", journey), "three_year_map", journey)

    save_progress(progress, path)
    loaded = load_progress(path, journey)

    assert loaded.completed_tasks == {"mdna"}
    assert loaded.completed_bosses == {"three_year_map"}


def test_unknown_progress_id_fails_explicitly():
    journey = default_journey()

    with pytest.raises(ValueError, match="unknown RPG task id"):
        toggle_task(RpgProgress(), "missing", journey)

    with pytest.raises(ValueError, match="unknown RPG boss id"):
        toggle_boss(RpgProgress(), "missing", journey)
