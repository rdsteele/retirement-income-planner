"""Pydantic models for the total-cost route."""

from pydantic import BaseModel, Field


class TotalCostRequest(BaseModel):
    # Fixed income fields
    pension: float = Field(default=0.0, ge=0)
    interest: float = Field(default=0.0, ge=0)
    ordinary_dividends: float = Field(default=0.0, ge=0)
    inherited_ira_rmd: float = Field(default=0.0, ge=0)
    ss_benefit: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    fixed_ltcg: float = Field(default=0.0, ge=0)
    tax_exempt_interest: float = Field(default=0.0, ge=0)
    above_the_line_adjustments: float = Field(default=0.0, ge=0)
    additional_deductions: float = Field(default=0.0, ge=0)

    # Mode and sweep fields
    sweep_mode: str
    variable_ordinary: float = Field(default=0.0, ge=0)
    sweep_floor: float = Field(default=0.0, ge=0)
    sweep_ceiling: float | None = Field(default=None, gt=0)
    sweep_step: float = Field(default=100.0, gt=0)
    filing_status: str
    tax_year: int = Field(gt=0)

    # Ohio fields
    include_ohio: bool = False
    ohio_medical_deduction: float = Field(default=0.0, ge=0)
    ohio_qualifying_retirement_income: float = Field(default=0.0, ge=0)

    # ACA fields
    include_aca: bool = False
    aptc_monthly: float = Field(default=0.0, ge=0)
    silver_premium_monthly: float = Field(default=0.0, ge=0)


class TotalCostComponents(BaseModel):
    ordinary: list[float]
    ss_torpedo: list[float]
    pref_stacking: list[float]
    niit: list[float]
    ohio: list[float]
    aca: list[float]


class TotalCostPoints(BaseModel):
    income: list[float]
    total_tax: list[float]
    emr: list[float]
    components: TotalCostComponents
    ss_taxable: list[float]
    ss_inclusion_rate: list[float]
    taxable_ordinary: list[float]
    ohio_tax: list[float]
    aca_magi: list[float]
    aptc_annual: list[float]
    aca_subsidy_loss: list[float]
    emr_aca: list[float]
    total_cost_emr: list[float]


class BracketBoundary(BaseModel):
    sweep_value: float
    rate: float
    notes: str


class TotalCostPlanningSignals(BaseModel):
    zero_ordinary_space: float | None
    zero_rate_threshold: float | None
    aca_cliff_sweep_value: float | None
    bracket_boundaries: list[BracketBoundary]
    ltcg_0pct_remaining: float | None
    torpedo_active: bool
    ss_fully_taxable: bool
    distance_to_22pct: float | None
    distance_to_24pct: float | None


class TotalCostResponse(BaseModel):
    sweep_mode: str
    filing_status: str
    tax_year: int
    points: TotalCostPoints
    irmaa_thresholds: list[float]
    aca_cliff_magi: float
    aptc_annual_max: float
    cliff_sweep_value: float
    planning_signals: TotalCostPlanningSignals
