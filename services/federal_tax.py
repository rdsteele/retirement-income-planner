"""Federal income tax calculation service.

Applies IRS preferential income stacking rules:
- Ordinary income fills brackets from the bottom.
- LTCG + qualified dividends stack on top of ordinary income and are taxed
  using the preferential (LTCG) rate schedule.

This service receives pre-computed taxable income. Deductions, Social Security
taxability, NIIT, and AMT are out of scope.
"""

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
import json

from services.common import round_rate, round_tax

_DATA_DIR = Path(__file__).parent.parent / "data" / "brackets"


@dataclass
class BracketDetail:
    rate: Decimal
    income_taxed: Decimal
    tax_amount: Decimal


@dataclass
class FederalTaxResult:
    ordinary_income_tax: Decimal
    preferential_income_tax: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    marginal_bracket_rate: Decimal
    bracket_breakdown: list[BracketDetail]


@lru_cache(maxsize=None)
def _load_brackets(tax_year: int) -> dict:
    path = _DATA_DIR / f"federal_{tax_year}.json"
    if not path.exists():
        raise ValueError(f"Unsupported tax year: {tax_year}")
    with path.open() as f:
        return json.load(f)


def _apply_ordinary_brackets(
    ordinary_income: Decimal,
    brackets: list[dict],
) -> tuple[Decimal, Decimal, list[BracketDetail]]:
    """Return (ordinary_tax, marginal_rate, breakdown) for ordinary income."""
    breakdown: list[BracketDetail] = []
    residual = ordinary_income
    marginal_rate = Decimal("0.10")  # default when ordinary_income is zero

    for bracket in brackets:
        if residual <= 0:
            break
        rate = Decimal(bracket["rate"])
        b_from = Decimal(bracket["from"])
        b_to = Decimal(bracket["to"]) if bracket["to"] is not None else None
        bracket_range = (b_to - b_from) if b_to is not None else residual
        income_taxed = min(residual, bracket_range)
        if income_taxed > 0:
            breakdown.append(
                BracketDetail(
                    rate=rate,
                    income_taxed=income_taxed,
                    tax_amount=round_tax(income_taxed * rate),
                )
            )
            marginal_rate = rate
            residual -= income_taxed

    ordinary_tax = sum((b.tax_amount for b in breakdown), Decimal("0"))
    return ordinary_tax, marginal_rate, breakdown


def _apply_preferential_brackets(
    preferential_income: Decimal,
    ordinary_income: Decimal,
    brackets: list[dict],
) -> Decimal:
    """Return tax on preferential income stacked on top of ordinary income."""
    pref_tax = Decimal("0")
    remaining_pref = preferential_income
    stack_base = ordinary_income

    for bracket in brackets:
        if remaining_pref <= 0:
            break
        rate = Decimal(bracket["rate"])
        b_from = Decimal(bracket["from"])
        b_to = Decimal(bracket["to"]) if bracket["to"] is not None else None
        bracket_start = max(stack_base, b_from)
        if b_to is not None:
            if bracket_start >= b_to:
                continue
            available = b_to - bracket_start
        else:
            available = remaining_pref  # top bracket absorbs all remaining
        income_taxed = min(remaining_pref, available)
        pref_tax += round_tax(income_taxed * rate)
        remaining_pref -= income_taxed

    return pref_tax


def calculate_federal_tax(
    ordinary_income: Decimal,
    preferential_income: Decimal,
    filing_status: str,
    tax_year: int,
) -> FederalTaxResult:
    if filing_status not in ("single", "mfj"):
        raise ValueError(f"Unsupported filing status: {filing_status!r}")

    data = _load_brackets(tax_year)
    ordinary_tax, marginal_rate, breakdown = _apply_ordinary_brackets(
        ordinary_income, data["ordinary"][filing_status]
    )
    pref_tax = _apply_preferential_brackets(
        preferential_income, ordinary_income, data["preferential"][filing_status]
    )

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
    )