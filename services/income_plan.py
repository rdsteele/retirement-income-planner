"""Income planning service.

Computes live plan summary (MAGI, income breakdown, shortfall, ACA distance)
and assembles the augmented sweep inputs needed by the total-cost service.

This service is the authoritative home for all income-plan business logic that
previously lived in income.html JavaScript. It composes social_security for SS
taxability so both the live summary and the EMR sweep use the same formula.
"""

from dataclasses import dataclass
from decimal import Decimal

from services.common import round_tax
from services.social_security import calculate_social_security_taxability

_ZERO = Decimal("0")
_D = Decimal


# ---------------------------------------------------------------------------
# Input data structures
# ---------------------------------------------------------------------------

@dataclass
class PlannedWithdrawal:
    """A planned withdrawal from a single holding or account."""
    account_type: str          # 'taxable', 'traditional', 'roth', 'hsa'
    amount: Decimal
    basis: Decimal = _ZERO     # relevant for taxable holdings only


@dataclass
class ExecutedWithdrawal:
    """A mid-year withdrawal already taken."""
    withdrawal_type: str       # 'ltcg', 'stcg', 'tax_deferred', 'tax_free_roth', 'tax_free_hsa'
    amount: Decimal
    basis: Decimal = _ZERO


@dataclass
class WithdrawalTotals:
    """Classified withdrawal totals used both by the summary and sweep assembly."""
    taxable_gains: Decimal           # LTCG from planned taxable + LTCG/STCG gains from executed
    taxable_basis: Decimal           # Basis portion of planned taxable withdrawals
    traditional: Decimal             # Planned traditional IRA/401k distributions
    roth: Decimal                    # Planned Roth withdrawals (MAGI-neutral)
    hsa: Decimal                     # Planned HSA medical withdrawals (MAGI-neutral)
    exec_ordinary: Decimal           # Executed withdrawals that are ordinary income
    exec_preferential: Decimal       # Executed withdrawals that are preferential income
    exec_taxable_amount: Decimal     # Gross executed taxable-account proceeds
    exec_traditional: Decimal        # Executed tax-deferred distributions
    exec_roth: Decimal               # Executed Roth withdrawals
    exec_hsa: Decimal                # Executed HSA withdrawals


@dataclass
class PlanSummary:
    """Live plan summary returned by compute_plan_summary."""
    magi: Decimal

    # Income breakdown
    forced_ordinary: Decimal        # pension_taxable + interest + ord_div + IRA dist + ss_taxable
    forced_preferential: Decimal    # qual_div + fixed_ltcg
    withdrawal_ordinary: Decimal    # planned traditional distributions
    withdrawal_preferential: Decimal  # planned taxable gains
    executed_ordinary: Decimal      # executed ordinary-income withdrawals
    executed_preferential: Decimal  # executed preferential-income withdrawals

    ss_taxable: Decimal             # computed by the real SS taxability service
    provisional_income: Decimal

    # Spending / shortfall
    total_spending: Decimal
    total_income: Decimal           # forced + withdrawal + executed (taxable portion)
    shortfall: Decimal | None       # None when no spending entered

    # ACA
    aca_distance: Decimal | None    # None when aca_cliff_magi is zero
    aca_cliff_magi: Decimal

    # Withdrawal totals (combined planned + executed per account type)
    total_taxable_withdrawals: Decimal
    total_traditional_withdrawals: Decimal
    total_roth_withdrawals: Decimal
    total_hsa_withdrawals: Decimal
    total_pension_annuity: Decimal
    total_ss_benefit: Decimal
    total_all_withdrawals: Decimal


# ---------------------------------------------------------------------------
# 1. Classify withdrawals
# ---------------------------------------------------------------------------

def classify_withdrawals(
    planned: list[PlannedWithdrawal],
    executed: list[ExecutedWithdrawal],
) -> WithdrawalTotals:
    """Classify planned and executed withdrawals into ordinary / preferential totals.

    Planned withdrawals:
      - taxable: basis is return-of-capital (MAGI-neutral for basis portion,
                 gain is preferential LTCG)
      - traditional: fully ordinary income
      - roth / hsa: MAGI-neutral

    Executed withdrawals:
      - ltcg: gain is preferential; basis is return-of-capital
      - stcg: gain is ordinary income; basis is return-of-capital
      - tax_deferred: fully ordinary income
      - tax_free_roth / tax_free_hsa: MAGI-neutral
    """
    taxable_gains = _ZERO
    taxable_basis = _ZERO
    traditional = _ZERO
    roth = _ZERO
    hsa = _ZERO

    for w in planned:
        if w.account_type == "taxable":
            effective_basis = min(w.basis, w.amount)
            gain = max(_ZERO, w.amount - effective_basis)
            taxable_gains += gain
            taxable_basis += effective_basis
        elif w.account_type == "traditional":
            traditional += w.amount
        elif w.account_type == "roth":
            roth += w.amount
        elif w.account_type == "hsa":
            hsa += w.amount

    exec_ordinary = _ZERO
    exec_preferential = _ZERO
    exec_taxable_amount = _ZERO
    exec_traditional = _ZERO
    exec_roth = _ZERO
    exec_hsa = _ZERO

    for ew in executed:
        gain = max(_ZERO, ew.amount - ew.basis)
        if ew.withdrawal_type == "ltcg":
            exec_preferential += gain
            exec_taxable_amount += ew.amount
        elif ew.withdrawal_type == "stcg":
            exec_ordinary += gain
            exec_taxable_amount += ew.amount
        elif ew.withdrawal_type == "tax_deferred":
            exec_ordinary += ew.amount
            exec_traditional += ew.amount
        elif ew.withdrawal_type == "tax_free_roth":
            exec_roth += ew.amount
        elif ew.withdrawal_type == "tax_free_hsa":
            exec_hsa += ew.amount

    return WithdrawalTotals(
        taxable_gains=taxable_gains,
        taxable_basis=taxable_basis,
        traditional=traditional,
        roth=roth,
        hsa=hsa,
        exec_ordinary=exec_ordinary,
        exec_preferential=exec_preferential,
        exec_taxable_amount=exec_taxable_amount,
        exec_traditional=exec_traditional,
        exec_roth=exec_roth,
        exec_hsa=exec_hsa,
    )


# ---------------------------------------------------------------------------
# 2. Compute plan summary (live, no sweep)
# ---------------------------------------------------------------------------

def _compute_agi_excluding_ss(
    pension_taxable: Decimal,
    interest: Decimal,
    ordinary_dividends: Decimal,
    ira_distributions: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    above_the_line_adjustments: Decimal,
    totals: WithdrawalTotals,
) -> Decimal:
    """AGI excluding Social Security — the input to the SS provisional income formula."""
    return (
        pension_taxable
        + interest
        + ordinary_dividends
        + ira_distributions
        + qualified_dividends
        + fixed_ltcg
        + totals.traditional
        + totals.taxable_gains
        + totals.exec_ordinary
        + totals.exec_preferential
        - above_the_line_adjustments
    )


def _compute_magi(
    pension_taxable: Decimal,
    interest: Decimal,
    ordinary_dividends: Decimal,
    ira_distributions: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    above_the_line_adjustments: Decimal,
    ss_taxable: Decimal,
    totals: WithdrawalTotals,
    tax_exempt_interest: Decimal,
) -> Decimal:
    """ACA MAGI = AGI + tax-exempt interest."""
    agi = (
        pension_taxable
        + interest
        + ordinary_dividends
        + ira_distributions
        + qualified_dividends
        + fixed_ltcg
        + totals.traditional
        + totals.taxable_gains
        + totals.exec_ordinary
        + totals.exec_preferential
        + ss_taxable
        - above_the_line_adjustments
    )
    return agi + tax_exempt_interest


def _compute_shortfall(
    total_spending: Decimal,
    estimated_taxes: Decimal,
    above_the_line_adjustments: Decimal,
    total_all_withdrawals: Decimal,
) -> Decimal | None:
    """Shortfall = expenses - all payments and withdrawals.

    ``total_all_withdrawals`` includes forced income (pension gross, SS, interest,
    dividends, IRA distributions, LTCG) plus planned and executed withdrawals, so
    there is no separate ``gross_forced_income`` term.

    Returns None when both spending and estimated taxes are zero (nothing entered yet).
    """
    if total_spending == _ZERO and estimated_taxes == _ZERO:
        return None
    total_expenses = total_spending + estimated_taxes + above_the_line_adjustments
    return round_tax(total_expenses - total_all_withdrawals)


def compute_plan_summary(
    *,
    filing_status: str,
    pension: Decimal,
    pension_taxable: Decimal,
    interest: Decimal,
    ordinary_dividends: Decimal,
    ira_distributions: Decimal,
    ss_benefit: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    above_the_line_adjustments: Decimal,
    tax_exempt_interest: Decimal,
    essential_spending: Decimal,
    discretionary_spending: Decimal,
    aca_cliff_magi: Decimal,
    estimated_taxes: Decimal,
    planned: list[PlannedWithdrawal],
    executed: list[ExecutedWithdrawal],
) -> PlanSummary:
    """Compute a live plan summary without running the full EMR sweep.

    Uses the real social_security service for SS taxability — accurate for both
    single and MFJ filers, unlike the single-filer approximation that previously
    lived in income.html JavaScript.
    """
    totals = classify_withdrawals(planned, executed)

    agi_excl_ss = _compute_agi_excluding_ss(
        pension_taxable, interest, ordinary_dividends, ira_distributions,
        qualified_dividends, fixed_ltcg, above_the_line_adjustments, totals,
    )

    ss_result = calculate_social_security_taxability(
        ss_benefit=ss_benefit,
        agi_excluding_ss=agi_excl_ss,
        tax_exempt_interest=tax_exempt_interest,
        filing_status=filing_status,
    )

    magi = _compute_magi(
        pension_taxable, interest, ordinary_dividends, ira_distributions,
        qualified_dividends, fixed_ltcg, above_the_line_adjustments,
        ss_result.taxable_ss, totals, tax_exempt_interest,
    )

    forced_ordinary = (
        pension_taxable + interest + ordinary_dividends + ira_distributions + ss_result.taxable_ss
    )
    forced_preferential = qualified_dividends + fixed_ltcg

    total_spending = essential_spending + discretionary_spending

    total_taxable_withdrawals = (
        totals.taxable_basis + totals.taxable_gains + totals.exec_taxable_amount
        + interest + ordinary_dividends + qualified_dividends + fixed_ltcg
        + tax_exempt_interest
    )
    total_traditional_withdrawals = totals.traditional + totals.exec_traditional + ira_distributions
    total_roth_withdrawals = totals.roth + totals.exec_roth
    total_hsa_withdrawals = totals.hsa + totals.exec_hsa
    total_pension_annuity = pension
    total_ss_benefit = ss_benefit
    total_all_withdrawals = (
        total_taxable_withdrawals
        + total_traditional_withdrawals
        + total_roth_withdrawals
        + total_hsa_withdrawals
        + total_pension_annuity
        + total_ss_benefit
    )

    forced_income = forced_ordinary + forced_preferential
    exec_income = totals.exec_ordinary + totals.exec_preferential
    withdrawal_income = totals.traditional + totals.taxable_gains
    total_income = forced_income + exec_income + withdrawal_income

    shortfall = _compute_shortfall(
        total_spending, estimated_taxes, above_the_line_adjustments,
        total_all_withdrawals,
    )

    aca_distance: Decimal | None = None
    if aca_cliff_magi > _ZERO:
        aca_distance = round_tax(aca_cliff_magi - magi)

    return PlanSummary(
        magi=round_tax(magi),
        forced_ordinary=round_tax(forced_ordinary),
        forced_preferential=round_tax(forced_preferential),
        withdrawal_ordinary=round_tax(totals.traditional),
        withdrawal_preferential=round_tax(totals.taxable_gains),
        executed_ordinary=round_tax(totals.exec_ordinary),
        executed_preferential=round_tax(totals.exec_preferential),
        ss_taxable=ss_result.taxable_ss,
        provisional_income=ss_result.provisional_income,
        total_spending=round_tax(total_spending),
        total_income=round_tax(total_income),
        shortfall=shortfall,
        aca_distance=aca_distance,
        aca_cliff_magi=aca_cliff_magi,
        total_taxable_withdrawals=round_tax(total_taxable_withdrawals),
        total_traditional_withdrawals=round_tax(total_traditional_withdrawals),
        total_roth_withdrawals=round_tax(total_roth_withdrawals),
        total_hsa_withdrawals=round_tax(total_hsa_withdrawals),
        total_pension_annuity=round_tax(total_pension_annuity),
        total_ss_benefit=round_tax(total_ss_benefit),
        total_all_withdrawals=round_tax(total_all_withdrawals),
    )


# ---------------------------------------------------------------------------
# 3. Assemble sweep inputs for /api/total-cost
# ---------------------------------------------------------------------------

def assemble_sweep_inputs(
    *,
    pension_taxable: Decimal,
    interest: Decimal,
    ordinary_dividends: Decimal,
    ira_distributions: Decimal,
    ss_benefit: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    above_the_line_adjustments: Decimal,
    tax_exempt_interest: Decimal,
    planned: list[PlannedWithdrawal],
    executed: list[ExecutedWithdrawal],
) -> dict[str, Decimal]:
    """Merge forced income with withdrawal totals into augmented sweep inputs.

    Returns a dict of Decimal values ready to pass to calculate_total_cost().
    The traditional distribution total and executed ordinary income are added to
    ira_distributions; taxable gains and executed preferential income are added
    to fixed_ltcg.  This mirrors the payload-assembly logic previously in JS.

    ``pension_taxable`` is passed as the ``pension`` key because the EMR sweep
    only uses the taxable portion for tax computation.
    """
    totals = classify_withdrawals(planned, executed)

    return {
        "pension": pension_taxable,
        "interest": interest,
        "ordinary_dividends": ordinary_dividends,
        "ira_distributions": ira_distributions + totals.traditional + totals.exec_ordinary,
        "ss_benefit": ss_benefit,
        "qualified_dividends": qualified_dividends,
        "fixed_ltcg": fixed_ltcg + totals.taxable_gains + totals.exec_preferential,
        "above_the_line_adjustments": above_the_line_adjustments,
        "tax_exempt_interest": tax_exempt_interest,
    }
