"""Pydantic models for the target-points routes."""

from pydantic import BaseModel, Field

from api.models.income_plan import IncomePlanRequest
from api.models.total_cost import TotalCostRequest


class TargetSettings(BaseModel):
    """The maximum acceptable EMR and the IRMAA settings, whatever the income request."""

    max_emr: float = Field(ge=0)
    include_irmaa: bool = True
    irmaa_enrollees: int | None = Field(default=None, ge=0)
    irmaa_inflation_rate: float | None = Field(default=None, ge=0)


class TargetPointsRequest(IncomePlanRequest, TargetSettings):
    """The income plan request (withdrawals folded in) plus the target settings."""


class SweepTargetPointsRequest(TotalCostRequest, TargetSettings):
    """The total cost sweep request (as the EMR page sends it) plus the target settings."""


class TargetLegResponse(BaseModel):
    from_income: float
    to_income: float
    average_emr: float
    cost: float
    causes: list[str]


class TargetPointsResponse(BaseModel):
    filing_status: str
    tax_year: int
    max_emr: float
    targets: list[float]
    legs: list[TargetLegResponse]
    irmaa_thresholds: list[float]  # IRMAA thresholds for the requested growth
