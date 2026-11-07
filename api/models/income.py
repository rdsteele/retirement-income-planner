"""Request fields shared by every route that takes income inputs."""

from decimal import Decimal

from pydantic import BaseModel, Field

from services.income_inputs import IncomeInputs


class IncomeInputsRequest(BaseModel):
    """The forced income and adjustments (see services.income_inputs.IncomeInputs).

    Adding an income field means adding it here and to IncomeInputs; the routes then
    pick it up through to_income_inputs().
    """

    pension: float = Field(default=0.0, ge=0)  # taxable portion
    wages: float = Field(default=0.0, ge=0)
    interest: float = Field(default=0.0, ge=0)
    ordinary_dividends: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    ira_distributions: float = Field(default=0.0, ge=0)
    other_investment_ordinary: float = Field(default=0.0, ge=0)
    ss_benefit: float = Field(default=0.0, ge=0)
    fixed_ltcg: float = Field(default=0.0, ge=0)
    tax_exempt_interest: float = Field(default=0.0, ge=0)
    above_the_line_adjustments: float = Field(default=0.0, ge=0)
    additional_deductions: float = Field(default=0.0, ge=0)
    taxpayer_65_plus: bool = False
    spouse_65_plus: bool = False

    def _taxable_pension(self) -> Decimal:
        return Decimal(str(self.pension))

    def to_income_inputs(self) -> IncomeInputs:
        return IncomeInputs.from_numbers(self.model_dump(), pension=self._taxable_pension())
