"""Pydantic models for the EMR route."""

from pydantic import BaseModel, Field

from api.models.income import IncomeInputsRequest


class EMRRequest(IncomeInputsRequest):
    # Mode and sweep fields
    sweep_mode: str
    filing_status: str
    tax_year: int = Field(gt=0)
    variable_ordinary: float = Field(default=0.0, ge=0)
    sweep_floor: float = Field(default=0.0, ge=0)
    sweep_ceiling: float | None = Field(default=None, gt=0)
    sweep_step: float | None = Field(default=None, gt=0)

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


class BracketDistance(BaseModel):
    rate: float
    distance: float | None


class PlanningSignals(BaseModel):
    zero_ordinary_space: float | None
    ltcg_0pct_remaining: float | None
    ltcg_0pct_ordinary_runway: float | None
    torpedo_active: bool
    ss_fully_taxable: bool
    bracket_distances: list[BracketDistance]


class EMRResponse(BaseModel):
    sweep_mode: str
    filing_status: str
    tax_year: int
    points: EMRPoints
    irmaa_thresholds: list[float]
    default_sweep_ceiling: float
    default_sweep_ceiling_rate: float
    planning_signals: PlanningSignals
