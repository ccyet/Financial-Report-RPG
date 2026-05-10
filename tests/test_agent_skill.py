from pathlib import Path


def test_financial_report_rpg_skill_exists_and_points_to_local_state():
    skill_path = Path("skills/financial-report-rpg/SKILL.md")

    assert skill_path.exists()
    content = skill_path.read_text(encoding="utf-8")
    assert "name: financial-report-rpg" in content
    assert ".local/rpg_progress.json" in content
    assert ".local/rpg_exports/progress.md" in content
    assert ".local/rpg_exports/progress.html" in content
    assert "Notion" in content


def test_financial_report_rpg_skill_is_conversation_first():
    content = Path("skills/financial-report-rpg/SKILL.md").read_text(encoding="utf-8")

    assert "对话" in content
    assert "关卡检验标准" in content
    assert "不满足标准" in content
    assert "打卡" in content
    assert "record_note" in content
    assert "next_check_in" in content
    assert "generate_html_report" in content
    assert "不要要求用户打开 Streamlit" in content
    assert "启动引导词" in content
    assert "不展示存储路径" in content
    assert "截图" in content
