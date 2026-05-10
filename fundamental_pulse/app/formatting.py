from __future__ import annotations

from datetime import datetime
from typing import Any

from fundamental_pulse.models import AnalysisRunResult, WatchlistRunResult


def format_pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value * 100:.2f}%"


def format_amount(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value / 10_000:,.2f} 万元"


def format_date(value: str | None) -> str:
    if not value:
        return "NA"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value[:16]


def format_error_summary(message: str | None) -> tuple[str, str]:
    detail = (message or "运行失败").strip()
    return detail[:32], detail


def build_result_kpis(result: AnalysisRunResult) -> dict[str, str]:
    return {
        "增长性质": result.classification,
        "质量评分": format_pct(result.validation_confidence_score),
        "报告期": result.period,
        "数据源": result.source,
        "运行状态": "完成",
    }


def build_history_table(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in history:
        score = entry.get("validation_confidence_score")
        rows.append(
            {
                "运行时间": format_date(_string_or_none(entry.get("created_at"))),
                "股票代码": str(entry.get("ticker") or "NA"),
                "报告期": str(entry.get("period") or "NA"),
                "数据源": str(entry.get("source") or "NA"),
                "增长性质": str(entry.get("classification") or "NA"),
                "质量评分": format_pct(float(score)) if isinstance(score, int | float) else "NA",
                "thesis": str(entry.get("thesis_status") or "NA"),
            }
        )
    return rows


def build_watchlist_table(result: WatchlistRunResult) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in result.items:
        rows.append(
            {
                "股票代码": item.ticker,
                "名称": item.name or "NA",
                "状态": item.status,
                "报告期": item.period or "NA",
                "增长性质": item.classification or "NA",
                "质量评分": format_pct(item.validation_confidence_score),
                "thesis": item.thesis_status or "NA",
                "报告路径": item.report_path or "NA",
                "错误": item.error_summary or "",
            }
        )
    return rows


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
