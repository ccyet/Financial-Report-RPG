from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import typer

from fundamental_pulse.analysis import (
    attribute_profit_growth,
    calculate_metrics,
    classify_growth,
    normalize_to_single_quarter,
)
from fundamental_pulse.business import analyze_oil_gas_boundary, validate_financial_records
from fundamental_pulse.high_frequency import (
    MockHighFrequencyFactorAdapter,
    analyze_high_frequency_correlations,
    assess_next_quarter_outlook,
)
from fundamental_pulse.highfreq import mock_highfreq_signals, summarize_high_freq_signals
from fundamental_pulse.ifind_adapter import (
    IfindHighFrequencyFactorAdapter,
    IfindMcpAdapter,
    IfindMcpClient,
    IfindMcpConfig,
    MockIfindMcpAdapter,
)
from fundamental_pulse.models import AnalysisRequest, AnalysisRunResult
from fundamental_pulse.report import generate_markdown_report
from fundamental_pulse.report_store import append_run_result, write_report
from fundamental_pulse.thesis import load_thesis, verify_thesis


def run_analysis(request: AnalysisRequest) -> AnalysisRunResult:
    _validate_request_periods(request)
    resolved_source = _resolve_source(
        mock=request.mock,
        source=request.source,
        ifind_config=request.ifind_config,
    )
    config = (
        None
        if resolved_source == "mock"
        else IfindMcpConfig.from_sources(request.ifind_config, server_name=request.ifind_server)
    )
    adapter = (
        MockIfindMcpAdapter()
        if resolved_source == "mock"
        else IfindMcpAdapter(
            client=IfindMcpClient(config=config),
            quarterly_tool_name=request.ifind_quarterly_tool,
        )
    )
    fetch_start, fetch_end = _quarterly_fetch_bounds(
        period=request.period,
        start=request.start,
        end=request.end,
    )
    records = normalize_to_single_quarter(
        adapter.fetch_quarterly_records(request.ticker, start=fetch_start, end=fetch_end)
    )
    if not records:
        raise typer.BadParameter(f"No quarterly records found for {request.ticker}.")

    metrics = calculate_metrics(records)
    metrics_by_period = {item.period: item for item in metrics}
    records_by_period = {record.period: record for record in records}

    selected_period = request.period or fetch_end or max(records_by_period)
    current = records_by_period.get(selected_period)
    current_metrics = metrics_by_period.get(selected_period)
    if current is None or current_metrics is None:
        raise typer.BadParameter(
            f"Period {selected_period} is not available for {request.ticker}."
        )

    classification = classify_growth(current_metrics)
    validation = validate_financial_records(records, metrics)
    business_judgment = None
    high_frequency = None
    forward_outlook = None
    high_freq_summary = None
    attribution = None
    previous_same_quarter = records_by_period.get(_previous_year_period(selected_period))
    if previous_same_quarter is not None:
        attribution = attribute_profit_growth(current, previous_same_quarter)

    if request.industry is not None:
        normalized_industry = request.industry.lower()
        if normalized_industry != "oil-gas":
            raise typer.BadParameter("Only oil-gas industry scenario is supported in MVP.")
        _require_oil_gas_inputs(request)
        assert request.base_oil_price is not None
        assert request.oil_price_floor is not None
        assert request.oil_price_ceiling is not None
        assert request.profit_sensitivity_per_usd is not None
        assert request.valuation_multiple_low is not None
        assert request.valuation_multiple_high is not None
        business_judgment = analyze_oil_gas_boundary(
            records=records,
            current_period=selected_period,
            base_oil_price=request.base_oil_price,
            oil_price_floor=request.oil_price_floor,
            oil_price_ceiling=request.oil_price_ceiling,
            profit_sensitivity_per_usd=request.profit_sensitivity_per_usd,
            valuation_multiple_low=request.valuation_multiple_low,
            valuation_multiple_high=request.valuation_multiple_high,
        )

    if request.factor_set is not None:
        high_frequency_server = _resolve_high_frequency_server(request)
        high_frequency_config = (
            None
            if resolved_source == "mock"
            else IfindMcpConfig.from_sources(
                request.ifind_config,
                server_name=high_frequency_server,
            )
        )
        factor_adapter = (
            MockHighFrequencyFactorAdapter()
            if resolved_source == "mock"
            else IfindHighFrequencyFactorAdapter(
                client=IfindMcpClient(config=high_frequency_config),
                high_frequency_tool_name=request.ifind_high_frequency_tool,
            )
        )
        observations = factor_adapter.fetch_factor_observations(
            request.ticker,
            factor_set=request.factor_set,
        )
        high_frequency = analyze_high_frequency_correlations(
            ticker=request.ticker,
            metrics=metrics,
            observations=observations,
            target_metric=request.target_metric,
            max_lag_quarters=request.max_lag_quarters,
        )
        forward_outlook = assess_next_quarter_outlook(
            ticker=request.ticker,
            current_period=selected_period,
            correlation_report=high_frequency,
            observations=observations,
        )

    if request.with_highfreq:
        if resolved_source == "mock":
            high_freq_signals = mock_highfreq_signals(
                request.ticker,
                lookback_days=request.lookback_days,
            )
        else:
            high_frequency_config = IfindMcpConfig.from_sources(
                request.ifind_config,
                server_name=_resolve_high_frequency_server(request),
            )
            high_freq_signals = IfindMcpClient(
                config=high_frequency_config
            ).query_high_freq_signals(
                request.ticker,
                lookback_days=request.lookback_days,
                tool_name=request.ifind_high_frequency_tool,
                natural_query=request.highfreq_query,
            )
        high_freq_summary = summarize_high_freq_signals(high_freq_signals)

    thesis_report = None
    if request.thesis_file is not None:
        thesis = load_thesis(request.thesis_file)
        thesis_report = verify_thesis(
            thesis=thesis,
            ticker=request.ticker,
            metrics=current_metrics,
            highfreq_summary=high_freq_summary,
        )

    report = generate_markdown_report(
        current,
        current_metrics,
        classification,
        attribution,
        validation,
        business_judgment,
        high_frequency,
        forward_outlook,
        source_label="iFinD MCP" if resolved_source == "ifind" else None,
        start_period=fetch_start,
        end_period=fetch_end,
        high_freq_summary=high_freq_summary,
        thesis_report=thesis_report,
    )
    run_id = _new_run_id()
    reports_dir = Path(request.reports_dir)
    report_path = reports_dir / f"{request.ticker}_{selected_period}.md"
    archive_report_path = (
        reports_dir / "runs" / f"{run_id}_{request.ticker}_{selected_period}.md"
        if request.record_history
        else None
    )
    write_report(report, report_path=report_path, archive_report_path=archive_report_path)

    result = AnalysisRunResult(
        run_id=run_id,
        created_at=datetime.now().replace(microsecond=0).isoformat(),
        ticker=request.ticker,
        period=selected_period,
        source=resolved_source,
        report_path=str(report_path),
        archive_report_path=str(archive_report_path) if archive_report_path is not None else None,
        classification=classification.growth_type,
        validation_status=validation.status,
        validation_confidence_score=validation.confidence_score,
        highfreq_enabled=request.with_highfreq,
        highfreq_summary=high_freq_summary.get("summary") if high_freq_summary else None,
        thesis_file=str(request.thesis_file) if request.thesis_file is not None else None,
        thesis_status=thesis_report.summary_status if thesis_report else None,
        report=report,
    )
    if request.record_history:
        append_run_result(result, reports_dir=reports_dir)
    return result


def _validate_request_periods(request: AnalysisRequest) -> None:
    if request.period is not None:
        _validate_period(request.period)
    if request.start is not None:
        _validate_period(request.start)
    if request.end is not None:
        _validate_period(request.end)


def _validate_period(period: str) -> None:
    if len(period) != 6 or period[4] != "Q" or period[:4].isdigit() is False:
        raise typer.BadParameter("period must use YYYYQ1-YYYYQ4 format.")
    if period[5] not in {"1", "2", "3", "4"}:
        raise typer.BadParameter("period must use YYYYQ1-YYYYQ4 format.")


def _previous_year_period(period: str) -> str:
    _validate_period(period)
    return f"{int(period[:4]) - 1}Q{period[5]}"


def _quarterly_fetch_bounds(
    period: str | None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[str | None, str | None]:
    if start is not None or end is not None:
        return start, end
    if period is None:
        return None, None
    _validate_period(period)
    return f"{int(period[:4]) - 1}Q1", period


def _resolve_source(mock: bool, source: str | None, ifind_config: Path | None) -> str:
    if mock:
        return "mock"
    candidate = (source or os.getenv("PULSE_SOURCE") or "").lower()
    if not candidate:
        candidate = (
            "ifind"
            if ifind_config is not None
            or os.getenv("IFIND_MCP_CONFIG")
            or os.getenv("IFIND_MCP_URL")
            or Path("ifind.mcp.json").exists()
            else "mock"
        )
    if candidate not in {"mock", "ifind"}:
        raise typer.BadParameter("source must be mock or ifind.")
    return candidate


def _require_oil_gas_inputs(request: AnalysisRequest) -> None:
    missing = [
        name
        for name, value in {
            "--base-oil-price": request.base_oil_price,
            "--oil-price-floor": request.oil_price_floor,
            "--oil-price-ceiling": request.oil_price_ceiling,
            "--profit-sensitivity-per-usd": request.profit_sensitivity_per_usd,
            "--valuation-multiple-low": request.valuation_multiple_low,
            "--valuation-multiple-high": request.valuation_multiple_high,
        }.items()
        if value is None
    ]
    if missing:
        raise typer.BadParameter(
            "oil-gas scenario requires explicit assumptions: " + ", ".join(missing)
        )


def _resolve_high_frequency_server(request: AnalysisRequest) -> str | None:
    return (
        request.ifind_high_frequency_server
        or _fundamental_pulse_config_value(request.ifind_config, "highFrequencyServer")
        or request.ifind_server
    )


def _fundamental_pulse_config_value(config_path: Path | None, key: str) -> str | None:
    if config_path is None and Path("ifind.mcp.json").exists():
        config_path = Path("ifind.mcp.json")
    if config_path is None:
        return None
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    pulse_config = payload.get("fundamentalPulse")
    if not isinstance(pulse_config, dict):
        return None
    value = pulse_config.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")
