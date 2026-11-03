"""Tax detail service.

Composes social_security, federal_tax, niit, and ohio_tax into a point-in-time
tax breakdown: income flow, bracket-by-bracket federal detail, NIIT, optional
Ohio tax, and combined totals. Pure Python with no knowledge of the API layer.
"""

from dataclasses import dataclass
from decimal import Decimal

from services.common import round_rate, round_tax
from services.data_loader import load_federal_data
from services.federal_tax import FederalTaxResult, calculate_federal_tax, split_taxable_income
from services.niit import NIITResult, calculate_niit, sum_net_investment_income
from services.ohio_tax import OhioTaxResult, calculate_ohio_tax
from services.social_security import calculate_social_security_taxability

_ZERO = Decimal("0")


@dataclass
class TaxBracketRow:
    rate: Decimal
    bracket_from: Decimal
    bracket_to: Decimal | None  # None for the unbounded top bracket
    income_taxed: Decimal
    tax_amount: Decimal


@dataclass
class IncomeSummary:
    gross_ordinary_income: Decimal
    ss_taxable: Decimal
    above_the_line_adjustments: Decimal
    agi: Decimal
    standard_deduction: Decimal
    additional_deductions: Decimal
    taxable_ordinary: Decimal
    taxable_preferential: Decimal


@dataclass
class TaxDetailResult:
    income: IncomeSummary
    federal: FederalTaxResult
    ordinary_breakdown: list[TaxBracketRow]
    preferential_breakdown: list[TaxBracketRow]
    niit: NIITResult
    ohio: OhioTaxResult | None
    total_federal_tax: Decimal  # income tax plus NIIT
    total_niit: Decimal
    total_ohio_tax: Decimal
    total_tax: Decimal
    overall_effective_rate: Decimal


# ---------------------------------------------------------------------------
# Bracket breakdowns
# ---------------------------------------------------------------------------


def _bracket_row(bracket: dict, income_taxed: Decimal) -> TaxBracketRow:
    rate = Decimal(bracket["rate"])
    return TaxBracketRow(
        rate=rate,
        bracket_from=Decimal(bracket["from"]),
        bracket_to=None if bracket["to"] is None else Decimal(bracket["to"]),
        income_taxed=income_taxed,
        tax_amount=round_tax(income_taxed * rate),
    )


def _build_ordinary_breakdown(
    taxable_ordinary: Decimal, brackets: list[dict]
) -> list[TaxBracketRow]:
    """Return one row per ordinary bracket that holds income (or a single zero row)."""
    rows: list[TaxBracketRow] = []
    residual = taxable_ordinary
    for bracket in brackets:
        if bracket["to"] is not None:
            bracket_range = Decimal(bracket["to"]) - Decimal(bracket["from"])
            income_taxed = min(residual, bracket_range)
        else:
            income_taxed = residual
        residual -= income_taxed
        if income_taxed > _ZERO:
            rows.append(_bracket_row(bracket, income_taxed))
        if residual <= _ZERO:
            break
    return rows or [_bracket_row(brackets[0], _ZERO)]


def _build_preferential_breakdown(
    taxable_ordinary: Decimal,
    taxable_preferential: Decimal,
    brackets: list[dict],
) -> list[TaxBracketRow]:
    """Return rows for preferential income stacked on top of ordinary income."""
    rows: list[TaxBracketRow] = []
    remaining = taxable_preferential
    stack_base = taxable_ordinary
    for bracket in brackets:
        bracket_start = max(stack_base, Decimal(bracket["from"]))
        if bracket["to"] is not None:
            bracket_end = Decimal(bracket["to"])
            if bracket_start >= bracket_end:
                continue  # ordinary income fills this entire bracket
            available = bracket_end - bracket_start
        else:
            available = remaining
        income_taxed = min(remaining, available)
        remaining -= income_taxed
        if income_taxed > _ZERO:
            rows.append(_bracket_row(bracket, income_taxed))
        if remaining <= _ZERO:
            break
    return rows or [_bracket_row(brackets[0], _ZERO)]


# ---------------------------------------------------------------------------
# Calculation steps
# ---------------------------------------------------------------------------


def _compute_overall_rate(total_tax: Decimal, agi: Decimal) -> Decimal:
    return round_rate(total_tax / agi) if agi > _ZERO else _ZERO


def _calculate_ohio_if_included(
    include_ohio: bool,
    federal_agi: Decimal,
    gross_medical_expenses: Decimal,
    qualifying_retirement_income: Decimal,
    ss_taxable: Decimal,
    tax_year: int,
    filing_status: str,
) -> OhioTaxResult | None:
    if not include_ohio:
        return None
    return calculate_ohio_tax(
        federal_agi=federal_agi,
        gross_medical_expenses=gross_medical_expenses,
        qualifying_retirement_income=qualifying_retirement_income,
        ss_taxable_federal=ss_taxable,
        tax_year=tax_year,
        filing_status=filing_status,
    )


def calculate_tax_detail(
    *,
    filing_status: str,
    tax_year: int,
    pension: Decimal = _ZERO,
    interest: Decimal = _ZERO,
    ordinary_dividends: Decimal = _ZERO,
    qualified_dividends: Decimal = _ZERO,
    ira_distributions: Decimal = _ZERO,
    other_investment_ordinary: Decimal = _ZERO,
    ss_benefit: Decimal = _ZERO,
    fixed_ltcg: Decimal = _ZERO,
    tax_exempt_interest: Decimal = _ZERO,
    wages: Decimal = _ZERO,
    above_the_line_adjustments: Decimal = _ZERO,
    additional_deductions: Decimal = _ZERO,
    include_ohio: bool = False,
    gross_medical_expenses: Decimal = _ZERO,
    ohio_qualifying_retirement_income: Decimal = _ZERO,
) -> TaxDetailResult:
    gross_ordinary = (
        pension
        + interest
        + ordinary_dividends
        + ira_distributions
        + other_investment_ordinary
        + wages
    )
    total_preferential = qualified_dividends + fixed_ltcg

    ss_result = calculate_social_security_taxability(
        ss_benefit=ss_benefit,
        agi_excluding_ss=gross_ordinary + total_preferential - above_the_line_adjustments,
        tax_exempt_interest=tax_exempt_interest,
        filing_status=filing_status,
    )
    ss_taxable = ss_result.taxable_ss

    data = load_federal_data(tax_year)
    standard_deduction = Decimal(data["standard_deduction"][filing_status])
    total_ordinary = gross_ordinary + ss_taxable - above_the_line_adjustments
    taxable_ordinary, taxable_preferential = split_taxable_income(
        total_ordinary, total_preferential, standard_deduction + additional_deductions
    )
    federal = calculate_federal_tax(
        ordinary_income=taxable_ordinary,
        preferential_income=taxable_preferential,
        filing_status=filing_status,
        tax_year=tax_year,
    )

    agi = total_ordinary + total_preferential
    niit = calculate_niit(
        magi=agi,
        net_investment_income=sum_net_investment_income(
            interest=interest,
            ordinary_dividends=ordinary_dividends,
            other_investment_ordinary=other_investment_ordinary,
            qualified_dividends=qualified_dividends,
            fixed_ltcg=fixed_ltcg,
        ),
        filing_status=filing_status,
        tax_year=tax_year,
    )
    ohio = _calculate_ohio_if_included(
        include_ohio,
        agi,
        gross_medical_expenses,
        ohio_qualifying_retirement_income,
        ss_taxable,
        tax_year,
        filing_status,
    )

    total_federal_tax = federal.total_tax + niit.niit
    total_ohio_tax = ohio.ohio_tax if ohio is not None else _ZERO
    total_tax = total_federal_tax + total_ohio_tax

    return TaxDetailResult(
        income=IncomeSummary(
            gross_ordinary_income=gross_ordinary,
            ss_taxable=ss_taxable,
            above_the_line_adjustments=above_the_line_adjustments,
            agi=agi,
            standard_deduction=standard_deduction,
            additional_deductions=additional_deductions,
            taxable_ordinary=taxable_ordinary,
            taxable_preferential=taxable_preferential,
        ),
        federal=federal,
        ordinary_breakdown=_build_ordinary_breakdown(
            taxable_ordinary, data["ordinary"][filing_status]
        ),
        preferential_breakdown=_build_preferential_breakdown(
            taxable_ordinary, taxable_preferential, data["preferential"][filing_status]
        ),
        niit=niit,
        ohio=ohio,
        total_federal_tax=total_federal_tax,
        total_niit=niit.niit,
        total_ohio_tax=total_ohio_tax,
        total_tax=total_tax,
        overall_effective_rate=_compute_overall_rate(total_tax, agi),
    )
