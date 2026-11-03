"""Federal income tax calculation service.

Applies IRS preferential income stacking rules:
- Ordinary income fills brackets from the bottom.
- LTCG + qualified dividends stack on top of ordinary income and are taxed
  using the preferential (LTCG) rate schedule.

This service receives pre-computed taxable income. Deductions, Social Security
taxability, NIIT, and AMT are out of scope.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from services.common import round_rate, round_tax
from services.data_loader import load_federal_data


@dataclass
class BracketDetail:
    rate: Decimal
    income_taxed: Decimal
    tax_amount: Decimal
    bracket_from: Decimal
    bracket_to: Decimal | None  # None for the unbounded top bracket


@dataclass
class FederalTaxResult:
    ordinary_income_tax: Decimal
    preferential_income_tax: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    marginal_bracket_rate: Decimal
    bracket_breakdown: list[BracketDetail]
    preferential_breakdown: list[BracketDetail] = field(default_factory=list)


def make_bracket_detail(bracket: dict, income_taxed: Decimal) -> BracketDetail:
    """Build a breakdown row for one bracket and the income taxed within it."""
    rate = Decimal(bracket["rate"])
    return BracketDetail(
        rate=rate,
        income_taxed=income_taxed,
        tax_amount=round_tax(income_taxed * rate),
        bracket_from=Decimal(bracket["from"]),
        bracket_to=None if bracket["to"] is None else Decimal(bracket["to"]),
    )


def _apply_ordinary_brackets(
    ordinary_income: Decimal,
    brackets: list[dict],
) -> tuple[Decimal, Decimal, list[BracketDetail]]:
    """Return (ordinary_tax, marginal_rate, breakdown) for ordinary income."""
    breakdown: list[BracketDetail] = []
    residual = ordinary_income
    marginal_rate = Decimal(brackets[0]["rate"])  # default when ordinary_income is zero

    for bracket in brackets:
        if residual <= 0:
            break
        b_to = Decimal(bracket["to"]) if bracket["to"] is not None else None
        bracket_range = (b_to - Decimal(bracket["from"])) if b_to is not None else residual
        income_taxed = min(residual, bracket_range)
        if income_taxed > 0:
            breakdown.append(make_bracket_detail(bracket, income_taxed))
            marginal_rate = Decimal(bracket["rate"])
            residual -= income_taxed

    ordinary_tax = sum((b.tax_amount for b in breakdown), Decimal("0"))
    return ordinary_tax, marginal_rate, breakdown


def _apply_preferential_brackets(
    preferential_income: Decimal,
    ordinary_income: Decimal,
    brackets: list[dict],
) -> list[BracketDetail]:
    """Return breakdown rows for preferential income stacked on top of ordinary income."""
    breakdown: list[BracketDetail] = []
    remaining_pref = preferential_income
    stack_base = ordinary_income

    for bracket in brackets:
        if remaining_pref <= 0:
            break
        b_to = Decimal(bracket["to"]) if bracket["to"] is not None else None
        bracket_start = max(stack_base, Decimal(bracket["from"]))
        if b_to is not None:
            if bracket_start >= b_to:
                continue
            available = b_to - bracket_start
        else:
            available = remaining_pref  # top bracket absorbs all remaining
        income_taxed = min(remaining_pref, available)
        breakdown.append(make_bracket_detail(bracket, income_taxed))
        remaining_pref -= income_taxed

    return breakdown


def unused_deduction(ordinary_income: Decimal, deductions: Decimal) -> Decimal:
    """Return the portion of deductions that exceeds ordinary income (never negative)."""
    return max(Decimal("0"), deductions - ordinary_income)


def split_taxable_income(
    ordinary_income: Decimal,
    preferential_income: Decimal,
    deductions: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (taxable_ordinary, taxable_preferential) after applying deductions.

    Deductions reduce ordinary income first. Any excess then reduces preferential
    income (LTCG + qualified dividends), as in the IRS Qualified Dividends and
    Capital Gain Tax Worksheet. Neither result is ever negative.
    """
    taxable_ordinary = max(Decimal("0"), ordinary_income - deductions)
    excess = unused_deduction(ordinary_income, deductions)
    taxable_preferential = max(Decimal("0"), preferential_income - excess)
    return taxable_ordinary, taxable_preferential


def calculate_federal_tax(
    ordinary_income: Decimal,
    preferential_income: Decimal,
    filing_status: str,
    tax_year: int,
) -> FederalTaxResult:
    if filing_status not in ("single", "mfj"):
        raise ValueError(f"Unsupported filing status: {filing_status!r}")

    data = load_federal_data(tax_year)
    ordinary_tax, marginal_rate, breakdown = _apply_ordinary_brackets(
        ordinary_income, data["ordinary"][filing_status]
    )
    pref_breakdown = _apply_preferential_brackets(
        preferential_income, ordinary_income, data["preferential"][filing_status]
    )
    pref_tax = sum((b.tax_amount for b in pref_breakdown), Decimal("0"))

    total_tax = ordinary_tax + pref_tax
    total_income = ordinary_income + preferential_income
    effective_rate = round_rate(total_tax / total_income) if total_income else Decimal("0")

    return FederalTaxResult(
        ordinary_income_tax=ordinary_tax,
        preferential_income_tax=pref_tax,
        total_tax=total_tax,
        effective_rate=effective_rate,
        marginal_bracket_rate=marginal_rate,
        bracket_breakdown=breakdown,
        preferential_breakdown=pref_breakdown,
    )
