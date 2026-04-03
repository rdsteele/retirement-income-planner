"""Pydantic models for the income-plan routes."""

from pydantic import BaseModel, Field


class PlannedWithdrawalRequest(BaseModel):
    account_type: str                  # 'taxable', 'traditional', 'roth', 'hsa'
    amount: float = Field(default=0.0, ge=0)
    basis: float = Field(default=0.0, ge=0)


class ExecutedWithdrawalRequest(BaseModel):
    withdrawal_type: str               # 'ltcg', 'stcg', 'tax_deferred', 'tax_free_roth', 'tax_free_hsa'
    amount: float = Field(default=0.0, ge=0)
    basis: float = Field(default=0.0, ge=0)


class IncomePlanRequest(BaseModel):
    # Identity / filing
    filing_status: str
    tax_year: int = Field(gt=0)

    # Forced income streams
    pension: float = Field(default=0.0, ge=0)
    interest: float = Field(default=0.0, ge=0)
    ordinary_dividends: float = Field(default=0.0, ge=0)
    ira_distributions: float = Field(default=0.0, ge=0)
    ss_benefit: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    fixed_ltcg: float = Field(default=0.0, ge=0)
    tax_exempt_interest: float = Field(default=0.0, ge=0)
    above_the_line_adjustments: float = Field(default=0.0, ge=0)
    additional_deductions: float = Field(default=0.0, ge=0)

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
    sweep_ceiling: float = Field(default=150000.0, gt=0)
    sweep_step: float = Field(default=100.0, gt=0)
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
    shortfall: float | None          # None when no spending entered

    # ACA
    aca_distance: float | None       # None when aca_cliff_magi is zero
    aca_cliff_magi: float

    # Withdrawal totals (combined planned + executed per account type)
    total_taxable_withdrawals: float
    total_traditional_withdrawals: float
    total_roth_withdrawals: float
    total_hsa_withdrawals: float
    total_all_withdrawals: float
