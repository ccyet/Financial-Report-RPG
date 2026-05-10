from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fundamental_pulse.models import (
    InvestmentThesis,
    QuarterMetrics,
    ThesisDriver,
    ThesisDriverVerification,
    ThesisVerificationReport,
)


class ThesisValidationError(ValueError):
    pass


OPERATORS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}
PERCENT_METRIC_TOKENS = ("yoy", "qoq", "margin", "ratio", "delta", "growth")


def load_thesis(path: str | Path) -> InvestmentThesis:
    thesis_path = Path(path)
    if not thesis_path.exists():
        raise ThesisValidationError(f"thesis file not found: {thesis_path}")

    try:
        payload = _load_payload(thesis_path)
        return InvestmentThesis.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise ThesisValidationError(f"invalid thesis file {thesis_path}: {exc}") from exc


def verify_thesis(
    thesis: InvestmentThesis,
    ticker: str,
    metrics: QuarterMetrics,
    highfreq_summary: dict[str, Any] | None = None,
) -> ThesisVerificationReport:
    if thesis.ticker != ticker:
        raise ThesisValidationError(
            f"thesis ticker {thesis.ticker} does not match CLI ticker {ticker}"
        )
    if metrics.ticker != ticker:
        raise ThesisValidationError(
            f"metrics ticker {metrics.ticker} does not match CLI ticker {ticker}"
        )

    drivers = [
        _verify_driver(driver, metrics=metrics, highfreq_summary=highfreq_summary)
        for driver in thesis.drivers
    ]
    status = _summary_status(drivers)
    passed = sum(driver.status == "pass" for driver in drivers)
    failed = sum(driver.status == "fail" for driver in drivers)
    unknown = sum(driver.status == "unknown" for driver in drivers)
    return ThesisVerificationReport(
        ticker=ticker,
        period=metrics.period,
        thesis_name=thesis.name,
        summary_status=status,
        summary=f"{passed} 个 driver 通过，{failed} 个失败，{unknown} 个未知。",
        drivers=drivers,
    )


def _load_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(text)
    elif suffix in {".yml", ".yaml"}:
        payload = _parse_simple_yaml(text)
    else:
        raise ThesisValidationError("thesis file must be .json, .yml, or .yaml")
    if not isinstance(payload, dict):
        raise ThesisValidationError("thesis file must contain an object")
    return payload


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    current_list_key: str | None = None
    current_item: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped.endswith(":") and not stripped.startswith("- "):
            key = stripped[:-1].strip()
            if key == "drivers":
                payload[key] = []
                current_list_key = key
                current_item = None
            else:
                payload[key] = {}
                current_list_key = None
            continue

        if current_list_key == "drivers" and stripped.startswith("- "):
            if current_item is not None:
                payload[current_list_key].append(current_item)
            current_item = {}
            remainder = stripped[2:].strip()
            if remainder:
                key, value = _split_yaml_pair(remainder)
                current_item[key] = _parse_yaml_scalar(value)
            continue

        if current_list_key == "drivers" and current_item is not None and indent >= 2:
            key, value = _split_yaml_pair(stripped)
            current_item[key] = _parse_yaml_scalar(value)
            continue

        key, value = _split_yaml_pair(stripped)
        payload[key] = _parse_yaml_scalar(value)
        current_list_key = None
        current_item = None

    if current_list_key == "drivers" and current_item is not None:
        payload[current_list_key].append(current_item)

    return payload


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index]
    return line


def _split_yaml_pair(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ThesisValidationError(f"invalid yaml line: {text}")
    key, value = text.split(":", 1)
    key = key.strip()
    if not key:
        raise ThesisValidationError(f"invalid yaml line: {text}")
    return key, value.strip()


def _parse_yaml_scalar(value: str) -> Any:
    if value == "":
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]

    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    if normalized in {"null", "none"}:
        return None

    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _verify_driver(
    driver: ThesisDriver,
    metrics: QuarterMetrics,
    highfreq_summary: dict[str, Any] | None,
) -> ThesisDriverVerification:
    if driver.metric is not None:
        return _verify_metric_driver(driver, metrics)
    if driver.highfreq_side is not None:
        return _verify_highfreq_driver(driver, highfreq_summary)
    return ThesisDriverVerification(
        id=driver.id,
        name=driver.name,
        status="unknown",
        actual=None,
        expected="未配置 metric 或 highfreq_side",
        evidence="该 driver 缺少可验证字段。",
    )


def _verify_metric_driver(
    driver: ThesisDriver,
    metrics: QuarterMetrics,
) -> ThesisDriverVerification:
    assert driver.metric is not None
    expected = _metric_expected_text(driver)
    if not hasattr(metrics, driver.metric):
        return _unknown(
            driver,
            actual=None,
            expected=expected,
            evidence=f"指标不存在：{driver.metric}",
        )

    actual = getattr(metrics, driver.metric)
    if actual is None:
        return _unknown(driver, actual=None, expected=expected, evidence=f"{driver.metric} 缺失。")
    if driver.operator not in OPERATORS or driver.threshold is None:
        return _unknown(driver, actual=actual, expected=expected, evidence="判断条件不完整。")

    threshold = _to_float(driver.threshold)
    if threshold is None:
        return _unknown(driver, actual=actual, expected=expected, evidence="阈值不是有效数字。")

    passed = OPERATORS[driver.operator](float(actual), threshold)
    status = "pass" if passed else "fail"
    actual_text = _format_metric_value(driver.metric, float(actual))
    threshold_text = _format_metric_value(driver.metric, threshold)
    verb = "满足" if passed else "未满足"
    return ThesisDriverVerification(
        id=driver.id,
        name=driver.name,
        status=status,
        actual=actual,
        expected=expected,
        evidence=f"{driver.metric}={actual_text}，{verb} {driver.operator} {threshold_text}。",
    )


def _verify_highfreq_driver(
    driver: ThesisDriver,
    highfreq_summary: dict[str, Any] | None,
) -> ThesisDriverVerification:
    assert driver.highfreq_side is not None
    expected = _highfreq_expected_text(driver)
    if highfreq_summary is None:
        return _unknown(
            driver,
            actual=None,
            expected=expected,
            evidence="未提供高频经营信号，暂无法验证。",
        )

    actual = highfreq_summary.get(driver.highfreq_side)
    if actual in (None, ""):
        return _unknown(
            driver,
            actual=None,
            expected=expected,
            evidence=f"高频维度缺失：{driver.highfreq_side}",
        )

    actual_text = str(actual)
    if driver.expected is not None:
        passed = actual_text == driver.expected
        comparator = "等于"
        expected_value = driver.expected
    elif driver.expected_not is not None:
        passed = actual_text != driver.expected_not
        comparator = "不等于"
        expected_value = driver.expected_not
    else:
        return _unknown(driver, actual=actual_text, expected=expected, evidence="判断条件不完整。")

    status = "pass" if passed else "fail"
    verb = "满足" if passed else "未满足"
    return ThesisDriverVerification(
        id=driver.id,
        name=driver.name,
        status=status,
        actual=actual_text,
        expected=expected,
        evidence=f"{driver.highfreq_side}={actual_text}，{verb}{comparator} {expected_value}。",
    )


def _metric_expected_text(driver: ThesisDriver) -> str:
    threshold = driver.threshold if driver.threshold is not None else "?"
    return f"{driver.metric} {driver.operator or '?'} {threshold}"


def _highfreq_expected_text(driver: ThesisDriver) -> str:
    if driver.expected is not None:
        return f"{driver.highfreq_side} == {driver.expected}"
    if driver.expected_not is not None:
        return f"{driver.highfreq_side} != {driver.expected_not}"
    return f"{driver.highfreq_side} ?"


def _unknown(
    driver: ThesisDriver,
    actual: float | str | None,
    expected: str,
    evidence: str,
) -> ThesisDriverVerification:
    return ThesisDriverVerification(
        id=driver.id,
        name=driver.name,
        status="unknown",
        actual=actual,
        expected=expected,
        evidence=evidence,
    )


def _summary_status(drivers: list[ThesisDriverVerification]) -> str:
    if any(driver.status == "fail" for driver in drivers):
        return "fail"
    if any(driver.status == "unknown" for driver in drivers):
        return "unknown"
    return "pass"


def _to_float(value: float | str) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _format_metric_value(metric: str, value: float) -> str:
    if any(token in metric for token in PERCENT_METRIC_TOKENS):
        return f"{value * 100:.2f}%"
    return f"{value:.2f}"
