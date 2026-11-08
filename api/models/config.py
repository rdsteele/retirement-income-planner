"""Pydantic model for the config route."""

from pydantic import BaseModel


class FilingStatusOption(BaseModel):
    value: str
    label: str
    filers: int  # people on the return


class SeniorDeductionYears(BaseModel):
    first_year: int
    last_year: int


class ConfigResponse(BaseModel):
    irmaa_inflation_default: float
    y_axis_max_emr: float
    sweep_step_default: float
    irmaa_lookback_years: int
    income_plan_sweep_ceiling: float
    filing_statuses: list[FilingStatusOption]
    senior_deduction_years: SeniorDeductionYears
