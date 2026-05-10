from pathlib import Path

from financial_report_rpg.app.streamlit_app import RPG_PROGRESS_PATH, dashboard_tab_labels


def test_dashboard_is_rpg_only():
    assert dashboard_tab_labels() == ["RPG 旅程"]


def test_rpg_progress_is_local_only():
    assert RPG_PROGRESS_PATH == Path(".local/rpg_progress.json")
