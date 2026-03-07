"""Pydantic models for the EMR route."""

from pydantic import BaseModel, Field


class EMRRequest(BaseModel):
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
    filing_status: str
    tax_year: int = Field(gt=0)
    variable_ordinary: float = Field(default=0.0, ge=0)
    sweep_floor: float = Field(default=0.0, ge=0)
    sweep_ceiling: float | None = Field(default=None, gt=0)
    sweep_step: float = Field(default=100.0, gt=0)

    # Ohio fields
    include_ohio: bool = False
    ohio_medical_deduction: float = Field(default=0.0, ge=0)
    ohio_qualifying_retirement_income: float = Field(default=0.0, ge=0)


class EMRComponents(BaseModel):
    ordinary: list[float]
    ss_torpedo: list[float]
    pref_stacking: list[float]
    niit: list[float]
    ohio: list[float]


class EMRPoints(BaseModel):
    income: list[float]
    total_tax: list[float]
    emr: list[float]
    components: EMRComponents
    ss_taxable: list[float]
    ss_inclusion_rate: list[float]
    taxable_ordinary: list[float]
    ohio_tax: list[float]


class PlanningSignals(BaseModel):
    ltcg_0pct_remaining: float | None
    torpedo_active: bool
    ss_fully_taxable: bool
    distance_to_22pct: float | None
    distance_to_24pct: float | None


class EMRResponse(BaseModel):
    sweep_mode: str
    filing_status: str
    tax_year: int
    points: EMRPoints
    irmaa_thresholds: list[float]
    planning_signals: PlanningSignals
