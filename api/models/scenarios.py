"""Pydantic models for the scenarios route."""

from pydantic import BaseModel


class ScenarioMetaResponse(BaseModel):
    name: str
    saved_at: str


class CurrentScenarioResponse(BaseModel):
    name: str | None


class CurrentScenarioRequest(BaseModel):
    name: str | None


class ScenarioSweepInputsResponse(BaseModel):
    """A scenario's income inputs with planned and executed withdrawals folded in."""

    pension: float
    wages: float
    interest: float
    ordinary_dividends: float
    qualified_dividends: float
    ira_distributions: float
    other_investment_ordinary: float
    ss_benefit: float
    fixed_ltcg: float
    tax_exempt_interest: float
    above_the_line_adjustments: float
    additional_deductions: float
    taxpayer_65_plus: bool
    spouse_65_plus: bool
    claim_senior_deduction: bool
