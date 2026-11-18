"""Pydantic models for the target-points route."""

from pydantic import BaseModel, Field

from api.models.income_plan import IncomePlanRequest


class TargetPointsRequest(IncomePlanRequest):
    """The income plan request plus the maximum acceptable EMR and the IRMAA settings."""

    max_emr: float = Field(ge=0)
    include_irmaa: bool = True
    irmaa_enrollees: int | None = Field(default=None, ge=0)
    irmaa_inflation_rate: float | None = Field(default=None, ge=0)


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
    irmaa_thresholds: list[float]  # the thresholds the targets were placed with
