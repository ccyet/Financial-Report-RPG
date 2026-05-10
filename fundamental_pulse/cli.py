from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import typer

from fundamental_pulse.analysis import (
    calculate_metrics,
    normalize_to_single_quarter,
)
from fundamental_pulse.highfreq import parse_highfreq_response
from fundamental_pulse.ifind_adapter import (
    IfindMcpAdapter,
    IfindMcpClient,
    IfindMcpConfig,
    IfindMcpError,
    MockIfindMcpAdapter,
    parse_ifind_quarterly_response,
)
from fundamental_pulse.models import AnalysisRequest, AnalysisRunResult, QuarterMetrics
from fundamental_pulse.thesis import ThesisValidationError, load_thesis, verify_thesis
from fundamental_pulse.watchlist import WatchlistError, load_watchlist, run_watchlist
from fundamental_pulse.workflow import run_analysis

app = typer.Typer(no_args_is_help=True)
ifind_app = typer.Typer(no_args_is_help=True)
thesis_app = typer.Typer(no_args_is_help=True)
watchlist_app = typer.Typer(no_args_is_help=True)
app.add_typer(ifind_app, name="ifind")
app.add_typer(thesis_app, name="thesis")
app.add_typer(watchlist_app, name="watchlist")
IFIND_CONFIG_OPTION = typer.Option(
    None,
    "--ifind-config",
    help="Path to JSON config with mcpServers and fundamentalPulse sections.",
)
IFIND_SERVER_OPTION = typer.Option(
    None,
    "--ifind-server",
    help="Server key under mcpServers to use from config file.",
)
IFIND_HIGH_FREQUENCY_SERVER_OPTION = typer.Option(
    None,
    "--ifind-high-frequency-server",
    help="Server key under mcpServers for high-frequency factors.",
)
SOURCE_OPTION = typer.Option(
    None,
    "--source",
    help="Data source: mock or ifind. Defaults to PULSE_SOURCE, local iFinD config, or mock.",
)
START_OPTION = typer.Option(None, "--start", help="Start quarter period, e.g. 2022Q1.")
END_OPTION = typer.Option(None, "--end", help="End quarter period, e.g. 2024Q4.")
THESIS_FILE_OPTION = typer.Option(
    None,
    "--thesis-file",
    help="Local investment thesis YAML/JSON file.",
)
THESIS_FILE_REQUIRED_OPTION = typer.Option(
    ...,
    "--thesis-file",
    help="Local investment thesis YAML/JSON file.",
)
LIMIT_OPTION = typer.Option(None, "--limit", min=1, help="Maximum watchlist items to run.")


@app.callback()
def main() -> None:
    """Quarterly fundamental analysis CLI."""


@app.command()
def analyze(
    ticker: str,
    mock: bool = typer.Option(False, "--mock", help="Use mock iFinD MCP data."),
    source: str | None = SOURCE_OPTION,
    start: str | None = START_OPTION,
    end: str | None = END_OPTION,
    period: str | None = typer.Option(None, "--period", help="Quarter period, e.g. 2025Q4."),
    industry: str | None = typer.Option(
        None,
        "--industry",
        help="Optional industry scenario. Supported: oil-gas.",
    ),
    base_oil_price: float | None = typer.Option(
        None,
        "--base-oil-price",
        help="Base oil price for oil-gas scenario.",
    ),
    oil_price_floor: float | None = typer.Option(
        None,
        "--oil-price-floor",
        help="Lower oil price boundary for oil-gas scenario.",
    ),
    oil_price_ceiling: float | None = typer.Option(
        None,
        "--oil-price-ceiling",
        help="Upper oil price boundary for oil-gas scenario.",
    ),
    profit_sensitivity_per_usd: float | None = typer.Option(
        None,
        "--profit-sensitivity-per-usd",
        help="TTM profit change per USD oil price move.",
    ),
    valuation_multiple_low: float | None = typer.Option(
        None,
        "--valuation-multiple-low",
        help="Lower valuation multiple for scenario boundary.",
    ),
    valuation_multiple_high: float | None = typer.Option(
        None,
        "--valuation-multiple-high",
        help="Upper valuation multiple for scenario boundary.",
    ),
    factor_set: str | None = typer.Option(
        None,
        "--factor-set",
        help="Optional high-frequency factor set. Supported: catl, auto.",
    ),
    target_metric: str = typer.Option(
        "revenue_yoy",
        "--target-metric",
        help="Metric to correlate with high-frequency factors.",
    ),
    max_lag_quarters: int = typer.Option(
        1,
        "--max-lag-quarters",
        min=0,
        help="Maximum factor lead lag in quarters.",
    ),
    with_highfreq: bool = typer.Option(
        False,
        "--with-highfreq",
        help="Include high-frequency operating signal validation.",
    ),
    lookback_days: int = typer.Option(
        90,
        "--lookback-days",
        min=1,
        help="High-frequency signal lookback window in days.",
    ),
    highfreq_query: str | None = typer.Option(
        None,
        "--highfreq-query",
        help="Natural-language query for iFinD MCP skills high-frequency data.",
    ),
    thesis_file: Path | None = THESIS_FILE_OPTION,
    ifind_quarterly_tool: str | None = typer.Option(
        None,
        "--ifind-quarterly-tool",
        help="iFinD MCP tool name for quarterly records.",
    ),
    ifind_high_frequency_tool: str | None = typer.Option(
        None,
        "--ifind-high-frequency-tool",
        help="iFinD MCP tool name for high-frequency factors.",
    ),
    ifind_config: Path | None = IFIND_CONFIG_OPTION,
    ifind_server: str | None = IFIND_SERVER_OPTION,
    ifind_high_frequency_server: str | None = IFIND_HIGH_FREQUENCY_SERVER_OPTION,
) -> None:
    try:
        _analyze_impl(
            ticker=ticker,
            mock=mock,
            source=source,
            start=start,
            end=end,
            period=period,
            industry=industry,
            base_oil_price=base_oil_price,
            oil_price_floor=oil_price_floor,
            oil_price_ceiling=oil_price_ceiling,
            profit_sensitivity_per_usd=profit_sensitivity_per_usd,
            valuation_multiple_low=valuation_multiple_low,
            valuation_multiple_high=valuation_multiple_high,
            factor_set=factor_set,
            target_metric=target_metric,
            max_lag_quarters=max_lag_quarters,
            with_highfreq=with_highfreq,
            lookback_days=lookback_days,
            highfreq_query=highfreq_query,
            thesis_file=thesis_file,
            ifind_quarterly_tool=ifind_quarterly_tool,
            ifind_high_frequency_tool=ifind_high_frequency_tool,
            ifind_config=ifind_config,
            ifind_server=ifind_server,
            ifind_high_frequency_server=ifind_high_frequency_server,
        )
    except (IfindMcpError, ThesisValidationError) as exc:
        raise click.ClickException(str(exc)) from exc


def _analyze_impl(
    ticker: str,
    mock: bool,
    source: str | None,
    start: str | None,
    end: str | None,
    period: str | None,
    industry: str | None,
    base_oil_price: float | None,
    oil_price_floor: float | None,
    oil_price_ceiling: float | None,
    profit_sensitivity_per_usd: float | None,
    valuation_multiple_low: float | None,
    valuation_multiple_high: float | None,
    factor_set: str | None,
    target_metric: str,
    max_lag_quarters: int,
    with_highfreq: bool,
    lookback_days: int,
    highfreq_query: str | None,
    thesis_file: Path | None,
    ifind_quarterly_tool: str | None,
    ifind_high_frequency_tool: str | None,
    ifind_config: Path | None,
    ifind_server: str | None,
    ifind_high_frequency_server: str | None,
) -> None:
    result = run_analysis(
        AnalysisRequest(
            ticker=ticker,
            mock=mock,
            source=source,
            start=start,
            end=end,
            period=period,
            industry=industry,
            base_oil_price=base_oil_price,
            oil_price_floor=oil_price_floor,
            oil_price_ceiling=oil_price_ceiling,
            profit_sensitivity_per_usd=profit_sensitivity_per_usd,
            valuation_multiple_low=valuation_multiple_low,
            valuation_multiple_high=valuation_multiple_high,
            factor_set=factor_set,
            target_metric=target_metric,
            max_lag_quarters=max_lag_quarters,
            with_highfreq=with_highfreq,
            lookback_days=lookback_days,
            highfreq_query=highfreq_query,
            thesis_file=thesis_file,
            ifind_quarterly_tool=ifind_quarterly_tool,
            ifind_high_frequency_tool=ifind_high_frequency_tool,
            ifind_config=ifind_config,
            ifind_server=ifind_server,
            ifind_high_frequency_server=ifind_high_frequency_server,
        )
    )
    _echo_analysis_result(result)


def _echo_analysis_result(result: AnalysisRunResult) -> None:
    typer.echo(f"报告路径：{result.report_path}")
    typer.echo(f"增长分类：{result.classification}")
    typer.echo(
        f"数据验证：{result.validation_status} ({result.validation_confidence_score:.2f})"
    )
    if result.highfreq_summary is not None:
        typer.echo(f"高频经营信号：{result.highfreq_summary}")
    if result.thesis_status is not None:
        typer.echo(f"投资假设验证：{result.thesis_status}")


@watchlist_app.command("run")
def watchlist_run(
    watchlist_path: Path,
    mock: bool = typer.Option(False, "--mock", help="Use mock iFinD MCP data."),
    source: str | None = SOURCE_OPTION,
    limit: int | None = LIMIT_OPTION,
) -> None:
    """Run a configured watchlist."""
    try:
        watchlist = load_watchlist(watchlist_path)
        result = run_watchlist(watchlist, mock=mock, source=source, limit=limit)
    except WatchlistError as exc:
        raise click.ClickException(str(exc)) from exc

    typer.echo(f"观察列表：{result.name}")
    typer.echo(f"合计：{result.total}")
    typer.echo(f"成功：{result.succeeded}")
    typer.echo(f"失败：{result.failed}")
    for item in result.items:
        if item.status == "success":
            typer.echo(
                f"- {item.ticker} {item.name or ''}：success，"
                f"{item.period or 'NA'}，{item.classification or 'NA'}，{item.report_path or 'NA'}"
            )
        else:
            typer.echo(
                f"- {item.ticker} {item.name or ''}：failed，"
                f"{item.error_summary or '运行失败'}"
            )


@thesis_app.command("verify")
def thesis_verify(
    ticker: str,
    thesis_file: Path = THESIS_FILE_REQUIRED_OPTION,
    mock: bool = typer.Option(False, "--mock", help="Use mock iFinD MCP data."),
    source: str | None = SOURCE_OPTION,
    start: str | None = START_OPTION,
    end: str | None = END_OPTION,
    period: str | None = typer.Option(None, "--period", help="Quarter period, e.g. 2025Q4."),
    ifind_quarterly_tool: str | None = typer.Option(
        None,
        "--ifind-quarterly-tool",
        help="iFinD MCP tool name for quarterly records.",
    ),
    ifind_config: Path | None = IFIND_CONFIG_OPTION,
    ifind_server: str | None = IFIND_SERVER_OPTION,
) -> None:
    """Verify a local thesis file against quarterly metrics."""
    try:
        current_metrics = _load_current_metrics(
            ticker=ticker,
            mock=mock,
            source=source,
            start=start,
            end=end,
            period=period,
            ifind_quarterly_tool=ifind_quarterly_tool,
            ifind_config=ifind_config,
            ifind_server=ifind_server,
        )
        thesis = load_thesis(thesis_file)
        result = verify_thesis(
            thesis=thesis,
            ticker=ticker,
            metrics=current_metrics,
            highfreq_summary=None,
        )
    except (IfindMcpError, ThesisValidationError) as exc:
        raise click.ClickException(str(exc)) from exc

    typer.echo(f"投资假设验证：{result.summary_status}")
    typer.echo(f"报告期：{result.period}")
    typer.echo(result.summary)
    for driver in result.drivers:
        typer.echo(f"- {driver.name}：{driver.status}；{driver.evidence}")


def _load_current_metrics(
    ticker: str,
    mock: bool,
    source: str | None,
    start: str | None,
    end: str | None,
    period: str | None,
    ifind_quarterly_tool: str | None,
    ifind_config: Path | None,
    ifind_server: str | None,
) -> QuarterMetrics:
    if period is not None:
        _validate_period(period)
    if start is not None:
        _validate_period(start)
    if end is not None:
        _validate_period(end)

    resolved_source = _resolve_source(mock=mock, source=source, ifind_config=ifind_config)
    config = (
        None
        if resolved_source == "mock"
        else IfindMcpConfig.from_sources(ifind_config, server_name=ifind_server)
    )
    adapter = (
        MockIfindMcpAdapter()
        if resolved_source == "mock"
        else IfindMcpAdapter(
            client=IfindMcpClient(config=config),
            quarterly_tool_name=ifind_quarterly_tool,
        )
    )
    fetch_start, fetch_end = _quarterly_fetch_bounds(period=period, start=start, end=end)
    records = normalize_to_single_quarter(
        adapter.fetch_quarterly_records(ticker, start=fetch_start, end=fetch_end)
    )
    if not records:
        raise typer.BadParameter(f"No quarterly records found for {ticker}.")

    metrics_by_period = {item.period: item for item in calculate_metrics(records)}
    selected_period = period or fetch_end or max(record.period for record in records)
    current_metrics = metrics_by_period.get(selected_period)
    if current_metrics is None:
        raise typer.BadParameter(f"Period {selected_period} is not available for {ticker}.")
    return current_metrics


@ifind_app.command("ping")
def ifind_ping(
    ifind_config: Path | None = IFIND_CONFIG_OPTION,
    ifind_server: str | None = IFIND_SERVER_OPTION,
) -> None:
    """Check iFinD MCP connectivity without printing secrets."""
    try:
        config = IfindMcpConfig.from_sources(ifind_config, server_name=ifind_server)
        IfindMcpClient(config=config).ping()
    except IfindMcpError as exc:
        raise click.ClickException(str(exc)) from exc
    typer.echo("iFinD MCP 连接正常")


@ifind_app.command("tools")
def ifind_tools_nested(
    ifind_config: Path | None = IFIND_CONFIG_OPTION,
    ifind_server: str | None = IFIND_SERVER_OPTION,
) -> None:
    """List available iFinD MCP tools."""
    _echo_ifind_tools(ifind_config=ifind_config, ifind_server=ifind_server)


@ifind_app.command("pull-quarterly")
def ifind_pull_quarterly(
    ticker: str,
    start: str = typer.Option(..., "--start", help="Start quarter period, e.g. 2022Q1."),
    end: str = typer.Option(..., "--end", help="End quarter period, e.g. 2024Q4."),
    save_raw: bool = typer.Option(False, "--save-raw", help="Save sanitized raw response."),
    ifind_config: Path | None = IFIND_CONFIG_OPTION,
    ifind_server: str | None = IFIND_SERVER_OPTION,
) -> None:
    """Pull real iFinD quarterly financials and optionally save sanitized raw data."""
    _validate_period(start)
    _validate_period(end)
    try:
        config = IfindMcpConfig.from_sources(ifind_config, server_name=ifind_server)
        client = IfindMcpClient(config=config)
        raw = client.query_quarterly_financials_raw(ticker, start, end)
        raw_path = _save_sanitized_raw_if_requested(raw, ticker, start, end) if save_raw else None
        records = parse_ifind_quarterly_response(raw, ticker=ticker)
    except IfindMcpError as exc:
        raise click.ClickException(str(exc)) from exc

    typer.echo(f"返回记录数：{len(records)}")
    if records:
        typer.echo(f"报告期范围：{records[0].period} 至 {records[-1].period}")
    if raw_path is not None:
        typer.echo(f"原始响应已保存：{raw_path}")


@ifind_app.command("pull-highfreq")
def ifind_pull_highfreq(
    ticker: str,
    lookback_days: int = typer.Option(
        90,
        "--lookback-days",
        min=1,
        help="High-frequency signal lookback window in days.",
    ),
    save_raw: bool = typer.Option(False, "--save-raw", help="Save sanitized raw response."),
    ifind_high_frequency_tool: str | None = typer.Option(
        None,
        "--ifind-high-frequency-tool",
        help="iFinD MCP skills/query tool name for high-frequency signals.",
    ),
    natural_query: str | None = typer.Option(
        None,
        "--query",
        help="Natural-language query passed directly to the selected iFinD MCP skills tool.",
    ),
    ifind_config: Path | None = IFIND_CONFIG_OPTION,
    ifind_server: str | None = IFIND_SERVER_OPTION,
    ifind_high_frequency_server: str | None = IFIND_HIGH_FREQUENCY_SERVER_OPTION,
) -> None:
    """Pull real iFinD high-frequency operating signals."""
    high_frequency_server = (
        ifind_high_frequency_server
        or _fundamental_pulse_config_value(ifind_config, "highFrequencyServer")
        or ifind_server
    )
    try:
        config = IfindMcpConfig.from_sources(ifind_config, server_name=high_frequency_server)
        client = IfindMcpClient(config=config)
        selected_tool = client.resolve_high_freq_tool_name(tool_name=ifind_high_frequency_tool)
        raw = client.query_high_freq_signals_raw(
            ticker,
            lookback_days=lookback_days,
            tool_name=selected_tool,
            natural_query=natural_query,
        )
        raw_path = (
            _save_sanitized_highfreq_raw_if_requested(
                raw,
                ticker,
                lookback_days,
                server_name=high_frequency_server,
                tool_name=selected_tool,
                natural_query=natural_query,
            )
            if save_raw
            else None
        )
        signals = parse_highfreq_response(raw, ticker=ticker)
    except IfindMcpError as exc:
        raise click.ClickException(str(exc)) from exc

    typer.echo(f"高频工具：{selected_tool}")
    typer.echo(f"返回高频信号数：{len(signals)}")
    if raw_path is not None:
        typer.echo(f"原始响应已保存：{raw_path}")


@app.command("ifind-tools")
def ifind_tools(
    ifind_config: Path | None = IFIND_CONFIG_OPTION,
    ifind_server: str | None = IFIND_SERVER_OPTION,
) -> None:
    """List available tools from the configured iFinD MCP server."""
    _echo_ifind_tools(ifind_config=ifind_config, ifind_server=ifind_server)


def _echo_ifind_tools(
    ifind_config: Path | None,
    ifind_server: str | None,
) -> None:
    try:
        config = IfindMcpConfig.from_sources(ifind_config, server_name=ifind_server)
        tools = IfindMcpClient(config=config).list_tools()
    except IfindMcpError as exc:
        raise click.ClickException(str(exc)) from exc
    if not tools:
        typer.echo("未发现 iFinD MCP tools。")
        return

    for tool in tools:
        name = tool.get("name", "")
        description = tool.get("description", "")
        typer.echo(f"- {name}: {description}")


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


def _require_oil_gas_inputs(
    base_oil_price: float | None,
    oil_price_floor: float | None,
    oil_price_ceiling: float | None,
    profit_sensitivity_per_usd: float | None,
    valuation_multiple_low: float | None,
    valuation_multiple_high: float | None,
) -> None:
    missing = [
        name
        for name, value in {
            "--base-oil-price": base_oil_price,
            "--oil-price-floor": oil_price_floor,
            "--oil-price-ceiling": oil_price_ceiling,
            "--profit-sensitivity-per-usd": profit_sensitivity_per_usd,
            "--valuation-multiple-low": valuation_multiple_low,
            "--valuation-multiple-high": valuation_multiple_high,
        }.items()
        if value is None
    ]
    if missing:
        raise typer.BadParameter(
            "oil-gas scenario requires explicit assumptions: " + ", ".join(missing)
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


def _save_sanitized_raw_if_requested(
    raw: Any,
    ticker: str,
    start: str,
    end: str,
) -> Path:
    output_path = Path("data/raw") / f"ifind_{ticker.replace('.', '_')}_{start}_{end}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_sanitize_raw(raw), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _save_sanitized_highfreq_raw_if_requested(
    raw: Any,
    ticker: str,
    lookback_days: int,
    server_name: str | None = None,
    tool_name: str | None = None,
    natural_query: str | None = None,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_path = (
        Path("data/raw")
        / f"ifind_highfreq_{ticker.replace('.', '_')}_{lookback_days}d_{timestamp}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "debug": {
            "ticker": ticker,
            "lookback_days": lookback_days,
            "server": server_name,
            "tool": tool_name,
            "query": natural_query,
        },
        "raw": _sanitize_raw(raw),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _sanitize_raw(value: Any) -> Any:
    sensitive_fragments = ("authorization", "token", "secret", "cookie", "session", "account")
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if any(fragment in str(key).lower() for fragment in sensitive_fragments):
                continue
            sanitized[key] = _sanitize_raw(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_raw(item) for item in value]
    return value


if __name__ == "__main__":
    app()
