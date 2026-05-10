from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fundamental_pulse.models import (
    AnalysisRequest,
    Watchlist,
    WatchlistRunItem,
    WatchlistRunResult,
)
from fundamental_pulse.thesis import _parse_yaml_scalar, _split_yaml_pair, _strip_comment
from fundamental_pulse.workflow import run_analysis


class WatchlistError(ValueError):
    pass


def load_watchlist(path: str | Path) -> Watchlist:
    watchlist_path = Path(path)
    if not watchlist_path.exists():
        raise WatchlistError(f"watchlist file not found: {watchlist_path}")

    try:
        payload = _load_payload(watchlist_path)
        return _resolve_watchlist_paths(
            Watchlist.model_validate(payload),
            base_path=watchlist_path,
        )
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise WatchlistError(f"invalid watchlist file {watchlist_path}: {exc}") from exc


def run_watchlist(
    watchlist: Watchlist,
    *,
    mock: bool = False,
    source: str | None = None,
    limit: int | None = None,
    reports_dir: str | Path = Path("reports"),
) -> WatchlistRunResult:
    items = watchlist.items[:limit] if limit is not None else watchlist.items
    run_items: list[WatchlistRunItem] = []
    for item in items:
        try:
            request = _request_from_item(
                watchlist=watchlist,
                item=item,
                mock=mock,
                source=source,
                reports_dir=reports_dir,
            )
            result = run_analysis(request)
            run_items.append(
                WatchlistRunItem(
                    ticker=item.ticker,
                    name=item.name,
                    status="success",
                    period=result.period,
                    classification=result.classification,
                    validation_status=result.validation_status,
                    validation_confidence_score=result.validation_confidence_score,
                    thesis_status=result.thesis_status,
                    report_path=result.report_path,
                )
            )
        except Exception as exc:
            run_items.append(
                WatchlistRunItem(
                    ticker=item.ticker,
                    name=item.name,
                    status="failed",
                    error_summary=_short_error(str(exc)),
                    error_detail=str(exc),
                )
            )

    succeeded = sum(item.status == "success" for item in run_items)
    failed = sum(item.status == "failed" for item in run_items)
    return WatchlistRunResult(
        name=watchlist.name,
        total=len(run_items),
        succeeded=succeeded,
        failed=failed,
        items=run_items,
    )


def _request_from_item(
    watchlist: Watchlist,
    item: Any,
    mock: bool,
    source: str | None,
    reports_dir: str | Path,
) -> AnalysisRequest:
    defaults = watchlist.defaults
    return AnalysisRequest(
        ticker=item.ticker,
        mock=mock,
        source=source or defaults.source,
        period=item.period or defaults.period,
        start=item.start or defaults.start,
        end=item.end or defaults.end,
        with_highfreq=(
            item.with_highfreq if item.with_highfreq is not None else defaults.with_highfreq
        ),
        lookback_days=item.lookback_days or defaults.lookback_days,
        thesis_file=item.thesis_file,
        reports_dir=Path(reports_dir),
    )


def _load_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(text)
    elif suffix in {".yml", ".yaml"}:
        payload = _parse_watchlist_yaml(text)
    else:
        raise WatchlistError("watchlist file must be .json, .yml, or .yaml")
    if not isinstance(payload, dict):
        raise WatchlistError("watchlist file must contain an object")
    return payload


def _resolve_watchlist_paths(watchlist: Watchlist, base_path: Path) -> Watchlist:
    items = []
    for item in watchlist.items:
        thesis_file = _resolve_relative_file(item.thesis_file, base_path)
        items.append(item.model_copy(update={"thesis_file": thesis_file}))
    return watchlist.model_copy(update={"items": items})


def _resolve_relative_file(path: Path | None, base_path: Path) -> Path | None:
    if path is None or path.is_absolute() or path.exists():
        return path
    for parent in (base_path.parent, *base_path.parents):
        candidate = parent / path
        if candidate.exists():
            return candidate
    return path


def _parse_watchlist_yaml(text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    current_section: str | None = None
    current_item: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1].strip()
            current_section = section
            current_item = None
            payload[section] = [] if section == "items" else {}
            continue

        if current_section == "defaults" and indent >= 2:
            key, value = _split_yaml_pair(stripped)
            payload["defaults"][key] = _parse_yaml_scalar(value)
            continue

        if current_section == "items" and stripped.startswith("- "):
            if current_item is not None:
                payload["items"].append(current_item)
            current_item = {}
            remainder = stripped[2:].strip()
            if remainder:
                key, value = _split_yaml_pair(remainder)
                current_item[key] = _parse_yaml_scalar(value)
            continue

        if current_section == "items" and current_item is not None and indent >= 2:
            key, value = _split_yaml_pair(stripped)
            current_item[key] = _parse_yaml_scalar(value)
            continue

        key, value = _split_yaml_pair(stripped)
        payload[key] = _parse_yaml_scalar(value)
        current_section = None
        current_item = None

    if current_section == "items" and current_item is not None:
        payload["items"].append(current_item)
    return payload


def _short_error(message: str) -> str:
    text = message.strip() or "运行失败"
    return text[:32]
