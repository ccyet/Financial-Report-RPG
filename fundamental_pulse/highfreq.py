from __future__ import annotations

import json
import re
from typing import Any

from fundamental_pulse.ifind_adapter import IfindMcpResponseError
from fundamental_pulse.models import HighFreqSignal

DIRECTIONS = {"positive", "neutral", "negative", "unknown"}
SIDE_KEYS = ("revenue_side", "cost_side", "margin_side", "cashflow_side", "risk_side")
ROW_COLLECTION_KEYS = ("signals", "records", "rows", "items", "datas")
EXPLICIT_SIGNAL_NAME_KEYS = ("signal_name", "name", "名称", "事件")
EXPLICIT_VALUE_KEYS = ("value", "数值")
HIGHFREQ_METADATA_KEYS = {
    "ticker",
    "symbol",
    "证券代码",
    "证券简称",
    "date",
    "日期",
    "source",
    "数据来源",
    "signal_type",
    "type",
    "类别",
    "信号类型",
    "signal_name",
    "name",
    "名称",
    "事件",
    "direction",
    "方向",
    "影响",
    "evidence",
    "证据",
    "摘要",
    "内容",
    "text",
    "unit",
    "单位",
    "related_financial_item",
    "相关财务项",
    "confidence",
    "置信度",
}
FINANCIAL_SIGNAL_KEYWORDS = (
    "营业收入",
    "营业总收入",
    "营业成本",
    "营业总成本",
    "净利润",
    "营业利润",
    "现金流",
    "现金净流量",
    "应收账款",
    "存货",
    "合同负债",
    "资产",
    "负债",
    "费用",
    "收入",
    "成本",
    "毛利",
    "主营构成",
    "roe",
    "roa",
    "ttm",
)
SIGNAL_TYPE_KEYWORDS = {
    "risk": ("诉讼", "处罚", "减值", "违约", "停产", "安全事故", "舆情"),
    "policy": ("政策", "补贴", "关税", "监管规则", "产业政策"),
    "cashflow": (
        "应收",
        "存货",
        "回款",
        "合同负债",
        "预收",
        "渠道库存",
        "账期",
        "现金流",
        "现金净流量",
    ),
    "margin": (
        "毛利率",
        "产品结构",
        "价格竞争",
        "asp",
        "折扣",
        "促销",
        "盈利能力",
        "净利润率",
        "净利润／营业总收入",
        "净利润/营业总收入",
        "roe",
        "roa",
    ),
    "cost": (
        "原材料",
        "锂价",
        "硅料",
        "煤价",
        "铜价",
        "运费",
        "能源",
        "采购成本",
        "营业成本",
        "总成本",
        "成本",
    ),
    "revenue": (
        "销量",
        "出货量",
        "订单",
        "中标",
        "装机",
        "销售",
        "价格上涨",
        "需求",
        "出口",
        "营业收入",
        "总收入",
        "收入",
    ),
    "industry": ("行业景气", "开工率", "库存周期", "竞争格局", "产能"),
}
TYPE_ALIASES = {
    "收入": "revenue",
    "订单": "revenue",
    "成本": "cost",
    "利润率": "margin",
    "毛利率": "margin",
    "现金流": "cashflow",
    "风险": "risk",
    "政策": "policy",
    "行业": "industry",
}
DIRECTION_ALIASES = {
    "正面": "positive",
    "改善": "positive",
    "利好": "positive",
    "positive": "positive",
    "中性": "neutral",
    "持平": "neutral",
    "neutral": "neutral",
    "负面": "negative",
    "恶化": "negative",
    "利空": "negative",
    "negative": "negative",
    "未知": "unknown",
    "unknown": "unknown",
}
POSITIVE_TEXT = (
    "改善",
    "增长",
    "上升",
    "恢复",
    "成本下降",
    "成本回落",
    "原材料价格下降",
    "价格回落",
    "订单增加",
    "需求增强",
    "形成支持",
    "利好",
)
NEGATIVE_TEXT = (
    "恶化",
    "下滑",
    "承压",
    "减值",
    "库存增加",
    "回款变差",
    "处罚",
    "价格竞争",
    "产品价格下降",
    "不确定",
    "利空",
)
NEUTRAL_TEXT = ("持平", "稳定", "无明显变化", "未见明显恶化")


def normalize_signal_type(raw_type: str | None, signal_name: str | None = None) -> str:
    raw = (raw_type or "").strip()
    if raw in SIGNAL_TYPE_KEYWORDS or raw == "unknown":
        return raw
    if raw in TYPE_ALIASES:
        return TYPE_ALIASES[raw]

    text = f"{raw_type or ''} {signal_name or ''}".lower()
    for signal_type, keywords in SIGNAL_TYPE_KEYWORDS.items():
        if any(_keyword_matches(keyword, text) for keyword in keywords):
            return signal_type
    return "unknown"


def normalize_direction(raw_direction: str | None, text: str | None = None) -> str:
    raw = (raw_direction or "").strip().lower()
    if raw in DIRECTIONS:
        return raw
    if raw_direction and raw_direction.strip() in DIRECTION_ALIASES:
        return DIRECTION_ALIASES[raw_direction.strip()]

    normalized_text = (text or "").lower()
    if any(keyword.lower() in normalized_text for keyword in POSITIVE_TEXT):
        return "positive"
    if any(keyword.lower() in normalized_text for keyword in NEGATIVE_TEXT):
        return "negative"
    if any(keyword.lower() in normalized_text for keyword in NEUTRAL_TEXT):
        return "neutral"
    return "unknown"


def parse_highfreq_response(
    raw: dict[str, Any] | list[Any] | str,
    ticker: str,
) -> list[HighFreqSignal]:
    payload = _decode_raw(raw)
    rows = _extract_highfreq_rows(payload)
    return [_signal_from_row(row, ticker=ticker) for row in rows]


def summarize_high_freq_signals(signals: list[HighFreqSignal]) -> dict[str, Any]:
    summary = {key: _summarize_side(signals, key) for key in SIDE_KEYS}
    summary["summary"] = _summary_text(summary)
    summary["key_signals"] = [_signal_to_dict(signal) for signal in _key_signals(signals)]
    summary["operating_time_sections"] = [
        _signal_to_dict(signal) for signal in _operating_time_section_signals(signals)
    ]
    return summary


def mock_highfreq_signals(ticker: str, lookback_days: int = 90) -> list[HighFreqSignal]:
    del lookback_days
    return parse_highfreq_response(
        [
            {
                "ticker": ticker,
                "date": "2024-04-10",
                "signal_type": "revenue",
                "signal_name": "海外储能订单增加",
                "direction": "positive",
                "evidence": "近 90 天海外储能相关订单披露增加。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-12",
                "signal_type": "revenue",
                "signal_name": "动力电池装机量同比增长",
                "value": 52.1,
                "unit": "GWh",
                "direction": "positive",
                "evidence": "国内动力电池装机量延续同比增长，对动力电池收入形成支持。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-13",
                "signal_type": "revenue",
                "signal_name": "储能系统中标增加",
                "value": 12,
                "unit": "项",
                "direction": "positive",
                "evidence": "储能系统招中标项目披露增加，有助于验证储能需求。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-15",
                "signal_type": "cost",
                "signal_name": "主要原材料价格下降",
                "direction": "positive",
                "evidence": "碳酸锂等原材料价格较前期回落，对成本端形成支持。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-16",
                "signal_type": "cost",
                "signal_name": "碳酸锂价格低位运行",
                "value": 7.6,
                "unit": "万元/吨",
                "direction": "positive",
                "evidence": "电池级碳酸锂价格维持低位，对材料成本形成缓冲。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-18",
                "signal_type": "industry",
                "signal_name": "正极材料排产改善",
                "value": 86,
                "unit": "%",
                "direction": "positive",
                "evidence": "正极材料排产边际改善，反映产业链需求有恢复迹象。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-22",
                "signal_type": "margin",
                "signal_name": "产品价格竞争仍在持续",
                "direction": "negative",
                "evidence": "行业价格竞争对单位盈利形成压力。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-23",
                "signal_type": "margin",
                "signal_name": "电解液价格竞争",
                "value": 1.9,
                "unit": "万元/吨",
                "direction": "negative",
                "evidence": "电解液环节价格竞争延续，可能压制部分产业链利润率。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-25",
                "signal_type": "cashflow",
                "signal_name": "存货环比增加",
                "direction": "negative",
                "evidence": "库存增加，需要观察是否为备货或需求放缓。",
            },
            {
                "ticker": ticker,
                "date": "2024-04-28",
                "signal_type": "cashflow",
                "signal_name": "产业链账期压力",
                "direction": "negative",
                "evidence": "部分下游客户账期仍偏长，需要继续观察回款节奏。",
            },
            {
                "ticker": ticker,
                "date": "2024-05-01",
                "signal_type": "risk",
                "signal_name": "海外政策不确定性",
                "direction": "negative",
                "evidence": "海外贸易政策变化可能影响订单节奏。",
            },
            {
                "ticker": ticker,
                "date": "2024-05-03",
                "signal_type": "risk",
                "signal_name": "欧洲关税政策不确定",
                "direction": "negative",
                "evidence": "欧洲贸易政策变化可能影响海外动力电池出货节奏。",
            },
            {
                "ticker": ticker,
                "date": "2024-05-05",
                "signal_type": "industry",
                "signal_name": "新能源车需求稳定",
                "direction": "neutral",
                "evidence": "行业需求未见明显恶化。",
            },
            {
                "ticker": ticker,
                "date": "2024-05-08",
                "signal_type": "policy",
                "signal_name": "产业政策延续支持",
                "direction": "positive",
                "evidence": "相关产业政策对长期需求形成支持。",
            },
            {
                "ticker": ticker,
                "date": "2024-05-10",
                "signal_type": "industry",
                "signal_name": "隔膜厂开工率稳定",
                "value": 72,
                "unit": "%",
                "direction": "neutral",
                "evidence": "隔膜环节开工率维持稳定，产业链未见明显恶化。",
            },
            {
                "ticker": ticker,
                "date": "2024-05-12",
                "signal_type": "margin",
                "signal_name": "产品结构改善",
                "direction": "positive",
                "evidence": "高端产品占比提升，对毛利率形成支持。",
            },
        ],
        ticker=ticker,
    )


def _decode_raw(raw: dict[str, Any] | list[Any] | str) -> Any:
    if not isinstance(raw, str):
        return raw
    stripped = raw.strip()
    if not stripped:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _parse_markdown_or_text(stripped)


def _keyword_matches(keyword: str, text: str) -> bool:
    normalized_keyword = keyword.lower()
    if normalized_keyword == "能源" and "新能源" in text:
        return False
    return normalized_keyword in text


def _extract_highfreq_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_ensure_dict(item) for item in payload]
    if not isinstance(payload, dict):
        raise IfindMcpResponseError("Unable to parse iFinD high-frequency response.")

    for key in ROW_COLLECTION_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [_ensure_dict(item) for item in value]

    data = payload.get("data")
    if isinstance(data, list):
        return [_ensure_dict(item) for item in data]
    if isinstance(data, dict):
        answer = data.get("answer")
        text = data.get("text")
        if isinstance(answer, str) and answer.strip():
            return _extract_highfreq_rows(_decode_raw(answer))
        if isinstance(text, str) and text.strip():
            return _extract_highfreq_rows(_decode_raw(text))
        for key in ROW_COLLECTION_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                return [_ensure_dict(item) for item in value]
        if isinstance(answer, str):
            return []

    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                return _extract_highfreq_rows(_decode_raw(item["text"]))

    return [_ensure_dict(payload)]


def _signal_from_row(row: dict[str, Any], ticker: str) -> HighFreqSignal:
    inferred_metric_key = _infer_metric_key(row)
    explicit_signal_name = _pick(row, *EXPLICIT_SIGNAL_NAME_KEYS, default=None)
    signal_name = _string_value(explicit_signal_name)
    if signal_name is None and inferred_metric_key is not None:
        signal_name = _clean_metric_name(inferred_metric_key)
    raw_type = _string_value(_pick(row, "signal_type", "type", "类别", "信号类型", default=None))
    explicit_value = _pick(row, *EXPLICIT_VALUE_KEYS, default=None)
    value = explicit_value
    if value is None and inferred_metric_key is not None:
        value = row.get(inferred_metric_key)
    evidence = _string_value(_pick(row, "evidence", "证据", "摘要", "内容", "text", default=None))
    if evidence is None and inferred_metric_key is not None and value not in (None, ""):
        evidence = f"{signal_name}={value}"
    raw_direction = _string_value(_pick(row, "direction", "方向", "影响", default=None))
    signal_type = normalize_signal_type(raw_type, signal_name)
    direction = normalize_direction(raw_direction, f"{signal_name or ''} {evidence or ''}")
    return HighFreqSignal(
        ticker=_string_value(_pick(row, "ticker", "symbol", "证券代码", default=ticker)) or ticker,
        date=_normalize_date_value(_pick(row, "date", "日期", default=None)),
        signal_type=signal_type,
        signal_name=signal_name or "unknown",
        value=value,
        unit=_string_value(_pick(row, "unit", "单位", default=None))
        or _unit_from_metric_key(inferred_metric_key),
        direction=direction,
        related_financial_item=_string_value(
            _pick(row, "related_financial_item", "相关财务项", default=None)
        ),
        source=_string_value(_pick(row, "source", "数据来源", default="ifind_mcp")) or "ifind_mcp",
        evidence=evidence,
        confidence=_pick(row, "confidence", "置信度", default=None),
    )


def _summarize_side(signals: list[HighFreqSignal], side_key: str) -> str:
    signal_types = {
        "revenue_side": {"revenue", "industry"},
        "cost_side": {"cost"},
        "margin_side": {"margin"},
        "cashflow_side": {"cashflow"},
        "risk_side": {"risk", "policy"},
    }[side_key]
    side_signals = [
        signal
        for signal in signals
        if signal.signal_type in signal_types and signal.direction != "unknown"
    ]
    if not side_signals:
        return "unknown"
    direction_scores = {"positive": 1, "neutral": 0, "negative": -1}
    score = sum(direction_scores.get(signal.direction, 0) for signal in side_signals)
    if score >= 1:
        return "positive"
    if score <= -1:
        return "negative"
    return "neutral"


def _summary_text(summary: dict[str, Any]) -> str:
    support = []
    pressure = []
    labels = {
        "revenue_side": "收入端",
        "cost_side": "成本端",
        "margin_side": "利润率",
        "cashflow_side": "现金流",
        "risk_side": "风险端",
    }
    for key, label in labels.items():
        if summary[key] == "positive":
            support.append(label)
        elif summary[key] == "negative":
            pressure.append(label)
    if not support and not pressure:
        return "高频数据不足，暂不能验证季度增长逻辑。"
    support_text = "、".join(support) if support else "暂无明确支持项"
    pressure_text = "、".join(pressure) if pressure else "暂无明确压力项"
    return f"高频数据对{support_text}有支持，但{pressure_text}存在压力。"


def _key_signals(signals: list[HighFreqSignal]) -> list[HighFreqSignal]:
    return sorted(signals, key=_signal_priority)[:8]


def _operating_time_section_signals(signals: list[HighFreqSignal]) -> list[HighFreqSignal]:
    candidates = [
        (index, signal)
        for index, signal in enumerate(signals)
        if signal.date is not None
        and signal.value not in (None, "")
        and signal.signal_type != "unknown"
        and not _is_financial_statement_signal(signal)
    ]
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (item[1].date, -item[0]),
        reverse=True,
    )
    return [signal for _, signal in sorted_candidates[:12]]


def _is_financial_statement_signal(signal: HighFreqSignal) -> bool:
    normalized_name = signal.signal_name.lower()
    return any(keyword in normalized_name for keyword in FINANCIAL_SIGNAL_KEYWORDS)


def _signal_priority(signal: HighFreqSignal) -> tuple[int, str]:
    if signal.direction == "negative" and signal.signal_type == "risk":
        return (0, _signal_sort_key(signal))
    if signal.direction == "negative" and signal.signal_type == "cashflow":
        return (1, _signal_sort_key(signal))
    if signal.direction == "negative" and signal.signal_type == "margin":
        return (2, _signal_sort_key(signal))
    if signal.direction == "positive" and signal.signal_type == "revenue":
        return (3, _signal_sort_key(signal))
    if signal.direction == "positive" and signal.signal_type == "cost":
        return (4, _signal_sort_key(signal))
    unknown_direction_type_rank = {
        "cashflow": 5,
        "revenue": 6,
        "cost": 7,
        "margin": 8,
        "risk": 9,
        "policy": 10,
        "industry": 11,
    }
    return (unknown_direction_type_rank.get(signal.signal_type, 12), _signal_sort_key(signal))


def _signal_sort_key(signal: HighFreqSignal) -> str:
    if signal.date is not None:
        return f"{signal.date.isoformat()} {signal.signal_name}"
    return signal.signal_name


def _signal_to_dict(signal: HighFreqSignal) -> dict[str, Any]:
    return {
        "date": signal.date.isoformat() if signal.date else None,
        "signal_type": signal.signal_type,
        "signal_name": signal.signal_name,
        "value": signal.value,
        "unit": signal.unit,
        "direction": signal.direction,
        "evidence": signal.evidence,
    }


def _parse_markdown_table(text: str) -> list[dict[str, Any]]:
    tables: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            current.append(line)
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)

    if not tables:
        raise IfindMcpResponseError("Unable to parse iFinD high-frequency response.")

    parsed_rows: list[dict[str, Any]] = []
    for table_rows in tables:
        if len(table_rows) < 3:
            continue
        headers = _split_markdown_row(table_rows[0])
        for row in table_rows[1:]:
            if _is_markdown_separator_row(row):
                continue
            cells = _split_markdown_row(row)
            if len(cells) == len(headers):
                parsed_rows.extend(
                    _expand_markdown_metric_row(dict(zip(headers, cells, strict=True)))
                )
    if not parsed_rows:
        raise IfindMcpResponseError("Unable to parse iFinD high-frequency response.")
    return parsed_rows


def _parse_markdown_or_text(text: str) -> list[dict[str, Any]]:
    try:
        return _parse_markdown_table(text)
    except IfindMcpResponseError:
        return [_plain_text_signal_row(text)]


def _plain_text_signal_row(text: str) -> dict[str, Any]:
    return {
        "signal_name": _plain_text_signal_name(text),
        "evidence": text,
        "direction": normalize_direction(None, text),
    }


def _plain_text_signal_name(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if len(first_line) <= 40:
        return first_line or "iFinD 高频文本"
    return first_line[:40]


def _split_markdown_row(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _is_markdown_separator_row(row: str) -> bool:
    cells = _split_markdown_row(row)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _expand_markdown_metric_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    if any(key in row for key in EXPLICIT_SIGNAL_NAME_KEYS):
        return [row]
    if not any(key in row for key in ("date", "日期")):
        return [row]

    metric_keys = [key for key in row if key not in HIGHFREQ_METADATA_KEYS]
    if not metric_keys:
        return [row]

    metadata = {key: value for key, value in row.items() if key in HIGHFREQ_METADATA_KEYS}
    expanded_rows = []
    for metric_key in metric_keys:
        signal_name = _clean_metric_name(metric_key) or metric_key
        value = row.get(metric_key)
        expanded_rows.append(
            {
                **metadata,
                "signal_name": signal_name,
                "value": value,
                "unit": _unit_from_metric_key(metric_key),
                "evidence": f"{signal_name}={value}" if value not in (None, "") else signal_name,
            }
        )
    return expanded_rows


def _pick(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return default


def _normalize_date_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if len(stripped) == 8 and stripped.isdigit():
        return f"{stripped[:4]}-{stripped[4:6]}-{stripped[6:]}"
    return value


def _infer_metric_key(row: dict[str, Any]) -> str | None:
    if not any(key in row for key in ("date", "日期")):
        return None
    candidates = [key for key in row if key not in HIGHFREQ_METADATA_KEYS]
    if len(candidates) != 1:
        return None
    return candidates[0]


def _clean_metric_name(metric_key: str | None) -> str | None:
    if metric_key is None:
        return None
    return re.sub(r"[（(]\s*单位\s*[:：]\s*[^）)]+[）)]", "", metric_key).strip()


def _unit_from_metric_key(metric_key: str | None) -> str | None:
    if metric_key is None:
        return None
    match = re.search(r"[（(]\s*单位\s*[:：]\s*([^）)]+)[）)]", metric_key)
    if not match:
        return None
    return match.group(1).strip()


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"value": value}


def _string_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
