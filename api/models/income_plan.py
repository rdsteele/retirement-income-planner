"""Pydantic models for the income-plan routes."""

from decimal import Decimal

from pydantic import BaseModel, Field

from api.models.income import IncomeInputsRequest


class PlannedWithdrawalRequest(BaseModel):
    account_type: str  # 'taxable', 'traditional', 'roth', 'hsa'
    amount: float = Field(default=0.0, ge=0)
    basis: float = Field(default=0.0, ge=0)


class ExecutedWithdrawalRequest(BaseModel):
    withdrawal_type: str  # 'ltcg', 'stcg', 'tax_deferred', 'tax_free_roth', 'tax_free_hsa'
    amount: float = Field(default=0.0, ge=0)
    basis: float = Field(default=0.0, ge=0)


class IncomePlanRequest(IncomeInputsRequest):
    """Income inputs plus spending, withdrawals, and sweep settings.

    Here ``pension`` is the gross payment (cash flow) and ``pension_taxable`` the part
    that is taxable; only the taxable part flows into the tax calculations.
    """

    # Identity / filing
    filing_status: str
    tax_year: int = Field(gt=0)

    pension_taxable: float = Field(default=0.0, ge=0)

    def _taxable_pension(self) -> Decimal:
        return Decimal(str(self.pension_taxable))

    # Spending
    essential_spending: float = Field(default=0.0, ge=0)
    discretionary_spending: float = Field(default=0.0, ge=0)

    # ACA
    include_aca: bool = False
    aca_cliff_magi: float = Field(default=0.0, ge=0)

    # Estimated taxes (from last Calculate run; 0 when stale)
    estimated_taxes: float = Field(default=0.0, ge=0)

    # Withdrawals
    planned_withdrawals: list[PlannedWithdrawalRequest] = Field(default_factory=list)
    executed_withdrawals: list[ExecutedWithdrawalRequest] = Field(default_factory=list)

    # Sweep parameters (used by calculate endpoint only)
    sweep_floor: float = Field(default=0.0, ge=0)
    sweep_ceiling: float | None = Field(default=None, gt=0)
    sweep_step: float | None = Field(default=None, gt=0)
    include_ohio: bool = True
    ohio_medical_deduction: float = Field(default=0.0, ge=0)
    ohio_qualifying_retirement_income: float = Field(default=0.0, ge=0)
    aptc_monthly: float = Field(default=0.0, ge=0)
    silver_premium_monthly: float = Field(default=0.0, ge=0)


# ── Summary response ──────────────────────────────────────────────────────


class PlanSummaryResponse(BaseModel):
    magi: float

    # Income breakdown
    forced_ordinary: float
    forced_preferential: float
    withdrawal_ordinary: float
    withdrawal_preferential: float
    executed_ordinary: float
    executed_preferential: float

    ss_taxable: float
    provisional_income: float

    # Spending / shortfall
    total_spending: float
    total_income: float
    shortfall: float | None  # None when no spending entered

    # ACA
    aca_distance: float | None  # None when aca_cliff_magi is zero
    aca_cliff_magi: float

    # Withdrawal totals (combined planned + executed per account type)
    total_taxable_withdrawals: float
    total_traditional_withdrawals: float
    total_roth_withdrawals: float
    total_hsa_withdrawals: float
    total_pension_annuity: float
    total_wages: float
    total_ss_benefit: float
    total_all_withdrawals: float
