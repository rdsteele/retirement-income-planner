"""Pydantic models for the tax detail route."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaxRequest(BaseModel):
    # Income fields
    pension: float = Field(default=0.0, ge=0)
    interest: float = Field(default=0.0, ge=0)
    ordinary_dividends: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    ira_distributions: float = Field(default=0.0, ge=0)
    ss_benefit: float = Field(default=0.0, ge=0)
    fixed_ltcg: float = Field(default=0.0, ge=0)
    tax_exempt_interest: float = Field(default=0.0, ge=0)
    wages: float = Field(default=0.0, ge=0)

    # Adjustment fields
    above_the_line_adjustments: float = Field(default=0.0, ge=0)
    additional_deductions: float = Field(default=0.0, ge=0)

    # Settings
    filing_status: Literal["single", "mfj"]
    tax_year: int = Field(gt=0)

    # Ohio fields
    include_ohio: bool = False
    gross_medical_expenses: float = Field(default=0.0, ge=0)
    ohio_qualifying_retirement_income: float = Field(default=0.0, ge=0)


class BracketRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rate: float
    bracket_from: float = Field(alias="from")
    to: float
    income_taxed: float
    tax_amount: float


class InputsSummary(BaseModel):
    gross_ordinary_income: float
    ss_taxable: float
    above_the_line_adjustments: float
    agi: float
    standard_deduction: float
    additional_deductions: float
    taxable_ordinary: float
    taxable_preferential: float


class FederalTaxDetail(BaseModel):
    ordinary_income_tax: float
    preferential_income_tax: float
    total_tax: float
    effective_rate: float
    marginal_bracket_rate: float
    bracket_breakdown: list[BracketRow]
    preferential_breakdown: list[BracketRow]


class OhioTaxDetail(BaseModel):
    included: bool
    ohio_agi: float | None = None
    personal_exemption: float | None = None
    medical_deduction: float | None = None
    ohio_tax_base: float | None = None
    tax_before_credits: float | None = None
    retirement_income_credit: float | None = None
    ohio_tax: float | None = None
    effective_rate: float | None = None


class TaxSummary(BaseModel):
    total_federal_tax: float
    total_ohio_tax: float
    total_tax: float
    overall_effective_rate: float


class TaxResponse(BaseModel):
    filing_status: str
    tax_year: int
    inputs_summary: InputsSummary
    federal: FederalTaxDetail
    ohio: OhioTaxDetail
    summary: TaxSummary
