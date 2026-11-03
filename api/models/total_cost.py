"""Pydantic models for the total-cost route."""

from pydantic import BaseModel, Field

from api.models.emr import BracketDistance
from api.models.income import IncomeInputsRequest


class TotalCostRequest(IncomeInputsRequest):
    # Mode and sweep fields
    sweep_mode: str
    variable_ordinary: float = Field(default=0.0, ge=0)
    sweep_floor: float = Field(default=0.0, ge=0)
    sweep_ceiling: float | None = Field(default=None, gt=0)
    sweep_step: float | None = Field(default=None, gt=0)
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
    ltcg_0pct_ordinary_runway: float | None
    torpedo_active: bool
    ss_fully_taxable: bool
    bracket_distances: list[BracketDistance]


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
