"""Tax detail service.

Composes social_security, federal_tax, niit, and ohio_tax into a point-in-time
tax breakdown: income flow, bracket-by-bracket federal detail, NIIT, optional
Ohio tax, and combined totals. Pure Python with no knowledge of the API layer.
"""

from dataclasses import dataclass
from decimal import Decimal

from services.aged_deduction import additional_standard_deduction
from services.common import round_rate
from services.data_loader import load_federal_data
from services.federal_tax import (
    BracketDetail,
    FederalTaxResult,
    calculate_federal_tax,
    make_bracket_detail,
    split_taxable_income,
)
from services.income_inputs import IncomeInputs
from services.niit import NIITResult, calculate_niit
from services.ohio_tax import OhioTaxResult, calculate_ohio_tax
from services.senior_deduction import senior_deduction
from services.social_security import calculate_social_security_taxability

_ZERO = Decimal("0")


@dataclass
class IncomeSummary:
    gross_ordinary_income: Decimal
    ss_taxable: Decimal
    above_the_line_adjustments: Decimal
    agi: Decimal
    standard_deduction: Decimal
    age_deduction: Decimal  # extra standard deduction for filers 65 or older
    senior_deduction: Decimal  # temporary senior deduction, after its income phase-out
    additional_deductions: Decimal
    taxable_ordinary: Decimal
    taxable_preferential: Decimal


@dataclass
class TaxDetailResult:
    income: IncomeSummary
    federal: FederalTaxResult
    ordinary_breakdown: list[BracketDetail]
    preferential_breakdown: list[BracketDetail]
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


def _ensure_row(rows: list[BracketDetail], brackets: list[dict]) -> list[BracketDetail]:
    """Return the rows, or a single zero row for the first bracket when there are none."""
    return rows or [make_bracket_detail(brackets[0], _ZERO)]


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
    income: IncomeInputs,
    filing_status: str,
    tax_year: int,
    include_ohio: bool = False,
    gross_medical_expenses: Decimal = _ZERO,
    ohio_qualifying_retirement_income: Decimal = _ZERO,
) -> TaxDetailResult:
    gross_ordinary = income.fixed_ordinary
    total_preferential = income.fixed_preferential
    above_the_line_adjustments = income.above_the_line_adjustments
    additional_deductions = income.additional_deductions

    ss_result = calculate_social_security_taxability(
        ss_benefit=income.ss_benefit,
        agi_excluding_ss=gross_ordinary + total_preferential - above_the_line_adjustments,
        tax_exempt_interest=income.tax_exempt_interest,
        filing_status=filing_status,
    )
    ss_taxable = ss_result.taxable_ss

    data = load_federal_data(tax_year)
    standard_deduction = Decimal(data["standard_deduction"][filing_status])
    age_deduction = additional_standard_deduction(income, filing_status, tax_year)
    total_ordinary = gross_ordinary + ss_taxable - above_the_line_adjustments
    agi = total_ordinary + total_preferential
    senior = senior_deduction(income, filing_status, tax_year, agi)
    taxable_ordinary, taxable_preferential = split_taxable_income(
        total_ordinary,
        total_preferential,
        standard_deduction + age_deduction + senior + additional_deductions,
    )
    federal = calculate_federal_tax(
        ordinary_income=taxable_ordinary,
        preferential_income=taxable_preferential,
        filing_status=filing_status,
        tax_year=tax_year,
    )

    niit = calculate_niit(
        magi=agi,
        net_investment_income=income.net_investment_income,
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
            age_deduction=age_deduction,
            senior_deduction=senior,
            additional_deductions=additional_deductions,
            taxable_ordinary=taxable_ordinary,
            taxable_preferential=taxable_preferential,
        ),
        federal=federal,
        ordinary_breakdown=_ensure_row(federal.bracket_breakdown, data["ordinary"][filing_status]),
        preferential_breakdown=_ensure_row(
            federal.preferential_breakdown, data["preferential"][filing_status]
        ),
        niit=niit,
        ohio=ohio,
        total_federal_tax=total_federal_tax,
        total_niit=niit.niit,
        total_ohio_tax=total_ohio_tax,
        total_tax=total_tax,
        overall_effective_rate=_compute_overall_rate(total_tax, agi),
    )
