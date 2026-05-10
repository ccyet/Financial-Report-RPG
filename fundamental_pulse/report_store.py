from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundamental_pulse.models import AnalysisRunResult

INDEX_FILE_NAME = "index.json"


def write_report(
    report: str,
    report_path: str | Path,
    archive_report_path: str | Path | None = None,
) -> None:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    if archive_report_path is None:
        return
    archive_path = Path(archive_report_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(report, encoding="utf-8")


def append_run_result(
    result: AnalysisRunResult,
    reports_dir: str | Path = Path("reports"),
) -> Path:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    index_path = reports_path / INDEX_FILE_NAME
    payload = _load_index_payload(index_path)
    entry = result.model_dump(mode="json", exclude={"report"})
    payload["runs"].insert(0, entry)
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index_path


def load_report_history(reports_dir: str | Path = Path("reports")) -> list[dict[str, Any]]:
    index_path = Path(reports_dir) / INDEX_FILE_NAME
    if not index_path.exists():
        return []
    return _load_index_payload(index_path)["runs"]


def read_report(report_path: str | Path) -> str:
    return Path(report_path).read_text(encoding="utf-8")


def _load_index_payload(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {"runs": []}
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), list):
        return {"runs": []}
    return payload
