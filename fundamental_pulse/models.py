from __future__ import annotations

from datetime import date as Date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class QuarterRecord(BaseModel):
    ticker: str
    period: str
    disclosure_date: str | None = None
    is_cumulative: bool = False
    unit: str = "CNY"

    revenue: float | None = None
    operating_cost: float | None = None

    selling_expense: float | None = None
    admin_expense: float | None = None
    rd_expense: float | None = None
    financial_expense: float | None = None

    net_profit_parent: float | None = None
    net_profit_deducted: float | None = None
    non_recurring_gain_loss: float | None = None
    operating_profit: float | None = None
    investment_income: float | None = None
    fair_value_change: float | None = None
    asset_impairment_loss: float | None = None
    credit_impairment_loss: float | None = None

    operating_cash_flow: float | None = None
    capex: float | None = None

    accounts_receivable: float | None = None
    inventory: float | None = None
    contract_liability: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None

    source: str = "mock_ifind_mcp"

    @property
    def report_period(self) -> str:
        return self.period


class QuarterMetrics(BaseModel):
    ticker: str
    period: str

    revenue_yoy: float | None = None
    revenue_qoq: float | None = None
    deducted_np_yoy: float | None = None
    deducted_np_qoq: float | None = None

    gross_margin: float | None = None
    gross_margin_delta_yoy: float | None = None

    expense_ratio: float | None = None
    expense_ratio_delta_yoy: float | None = None

    ocf_to_np: float | None = None
    non_recurring_ratio: float | None = None

    ar_growth_gap_vs_revenue: float | None = None
    inventory_growth_gap_vs_revenue: float | None = None


class GrowthClassification(BaseModel):
    growth_type: str
    explanation: str
    triggered_rules: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ProfitAttribution(BaseModel):
    ticker: str
    period: str
    profit_delta: float | None = None
    revenue_contribution: float | None = None
    gross_margin_contribution: float | None = None
    expense_contribution: float | None = None
    non_recurring_contribution: float | None = None
    top_positive: list[str] = Field(default_factory=list)
    top_negative: list[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    period: str | None = None
    field: str | None = None
    message: str


class DataValidationReport(BaseModel):
    status: Literal["pass", "warning", "fail"]
    confidence_score: float
    issues: list[ValidationIssue] = Field(default_factory=list)


class OilGasScenario(BaseModel):
    name: str
    oil_price: float
    profit_center: float
    valuation_low: float
    valuation_high: float


class OilGasBoundaryAnalysis(BaseModel):
    ticker: str
    period: str
    base_oil_price: float
    oil_price_floor: float
    oil_price_ceiling: float
    profit_sensitivity_per_usd: float
    valuation_multiple_low: float
    valuation_multiple_high: float
    base_profit_ttm: float
    scenarios: list[OilGasScenario] = Field(default_factory=list)
    conclusion: str


class HighFrequencyObservation(BaseModel):
    ticker: str
    factor_name: str
    factor_label: str
    date: str
    value: float
    frequency: Literal["daily", "weekly", "monthly"]
    source: str = "mock_high_frequency"


class HighFreqSignal(BaseModel):
    ticker: str
    date: Date | None = None
    signal_type: str
    signal_name: str
    value: str | float | None = None
    unit: str | None = None
    direction: str
    related_financial_item: str | None = None
    source: str = "ifind_mcp"
    evidence: str | None = None
    confidence: float | None = None


class HighFrequencyCorrelation(BaseModel):
    factor_name: str
    factor_label: str
    target_metric: str
    lag_quarters: int
    correlation: float
    observations: int
    direction: Literal["positive", "negative", "neutral"]
    interpretation: str


class HighFrequencyCorrelationReport(BaseModel):
    ticker: str
    target_metric: str
    sample_size: int
    correlations: list[HighFrequencyCorrelation] = Field(default_factory=list)
    conclusion: str


class ForwardFactorSignal(BaseModel):
    factor_name: str
    factor_label: str
    current_period: str
    forecast_period: str
    current_value: float
    forecast_value: float
    change_rate: float
    correlation: float
    expected_effect: Literal["support", "pressure", "neutral"]
    rationale: str


class ForwardOperatingOutlook(BaseModel):
    ticker: str
    current_period: str
    forecast_period: str
    target_metric: str
    outlook: Literal["改善", "走弱", "平稳", "数据不足"]
    confidence_score: float
    signals: list[ForwardFactorSignal] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    conclusion: str


class ThesisDriver(BaseModel):
    id: str
    name: str
    description: str | None = None
    metric: str | None = None
    operator: Literal[">=", ">", "<=", "<", "==", "!="] | None = None
    threshold: float | str | None = None
    highfreq_side: str | None = None
    expected: str | None = None
    expected_not: str | None = None
    required: bool = True


class InvestmentThesis(BaseModel):
    ticker: str
    name: str
    description: str | None = None
    drivers: list[ThesisDriver] = Field(default_factory=list)


class ThesisDriverVerification(BaseModel):
    id: str
    name: str
    status: Literal["pass", "fail", "unknown"]
    actual: float | str | None = None
    expected: str
    evidence: str


class ThesisVerificationReport(BaseModel):
    ticker: str
    period: str
    thesis_name: str
    summary_status: Literal["pass", "fail", "unknown"]
    summary: str
    drivers: list[ThesisDriverVerification] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    ticker: str
    mock: bool = False
    source: Literal["mock", "ifind"] | None = None
    start: str | None = None
    end: str | None = None
    period: str | None = None

    industry: str | None = None
    base_oil_price: float | None = None
    oil_price_floor: float | None = None
    oil_price_ceiling: float | None = None
    profit_sensitivity_per_usd: float | None = None
    valuation_multiple_low: float | None = None
    valuation_multiple_high: float | None = None

    factor_set: str | None = None
    target_metric: str = "revenue_yoy"
    max_lag_quarters: int = 1

    with_highfreq: bool = False
    lookback_days: int = 90
    highfreq_query: str | None = None

    thesis_file: Path | None = None

    ifind_quarterly_tool: str | None = None
    ifind_high_frequency_tool: str | None = None
    ifind_config: Path | None = None
    ifind_server: str | None = None
    ifind_high_frequency_server: str | None = None

    reports_dir: Path = Path("reports")
    record_history: bool = True


class AnalysisRunResult(BaseModel):
    run_id: str
    created_at: str
    ticker: str
    period: str
    source: Literal["mock", "ifind"]
    report_path: str
    archive_report_path: str | None = None
    classification: str
    validation_status: Literal["pass", "warning", "fail"]
    validation_confidence_score: float
    highfreq_enabled: bool = False
    highfreq_summary: str | None = None
    thesis_file: str | None = None
    thesis_status: Literal["pass", "fail", "unknown"] | None = None
    warnings: list[str] = Field(default_factory=list)
    report: str


class WatchlistItem(BaseModel):
    ticker: str
    name: str | None = None
    period: str | None = None
    start: str | None = None
    end: str | None = None
    with_highfreq: bool | None = None
    lookback_days: int | None = None
    thesis_file: Path | None = None


class WatchlistDefaults(BaseModel):
    source: Literal["mock", "ifind"] | None = None
    period: str | None = None
    start: str | None = None
    end: str | None = None
    with_highfreq: bool = False
    lookback_days: int = 90


class Watchlist(BaseModel):
    name: str
    description: str | None = None
    defaults: WatchlistDefaults = Field(default_factory=WatchlistDefaults)
    items: list[WatchlistItem] = Field(default_factory=list)


class WatchlistRunItem(BaseModel):
    ticker: str
    name: str | None = None
    status: Literal["success", "failed"]
    period: str | None = None
    classification: str | None = None
    validation_status: Literal["pass", "warning", "fail"] | None = None
    validation_confidence_score: float | None = None
    thesis_status: Literal["pass", "fail", "unknown"] | None = None
    report_path: str | None = None
    error_summary: str | None = None
    error_detail: str | None = None


class WatchlistRunResult(BaseModel):
    name: str
    total: int
    succeeded: int
    failed: int
    items: list[WatchlistRunItem] = Field(default_factory=list)
