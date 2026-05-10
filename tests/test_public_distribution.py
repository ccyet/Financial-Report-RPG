from pathlib import Path

TRACKED_PUBLIC_FILES = [
    Path("README.md"),
    Path("SKILL.md"),
    Path("skills/financial-report-rpg/SKILL.md"),
    Path("examples/MINIMAL-RUN.md"),
]


def test_root_skill_is_public_entrypoint():
    content = Path("SKILL.md").read_text(encoding="utf-8")

    assert "name: financial-report-rpg" in content
    assert "pyproject.toml" in content
    assert "uv run python -m financial_report_rpg.agent_cli next" in content
    assert "不要只复制 `skills/financial-report-rpg/`" in content


def test_workspace_skill_points_to_root_entrypoint():
    content = Path("skills/financial-report-rpg/SKILL.md").read_text(encoding="utf-8")

    assert "workspace 兼容入口" in content
    assert "仓库根目录 `SKILL.md`" in content
    assert "financial_report_rpg.agent_cli" in content


def test_public_docs_have_minimal_run_and_no_personal_paths():
    forbidden = ["/Users/" + "a1234", "fundamental" + " analysis", "OneDrive-" + "个人"]

    for path in TRACKED_PUBLIC_FILES:
        content = path.read_text(encoding="utf-8")
        assert content.strip()
        for token in forbidden:
            assert token not in content

    readme = Path("README.md").read_text(encoding="utf-8")
    minimal_run = Path("examples/MINIMAL-RUN.md").read_text(encoding="utf-8")
    assert "git clone https://github.com/ccyet/Financial-Report-RPG.git" in readme
    assert "openclaw skills check" in readme
    assert "开启 financial-report-rpg" in minimal_run
