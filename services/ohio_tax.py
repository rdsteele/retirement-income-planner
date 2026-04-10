"""Ohio state income tax calculation service.

Handles Ohio-specific rules: AGI-tiered personal exemption, medical expense
deduction with 7.5% AGI floor, Social Security exemption, progressive bracket
tax using Ohio's cumulative formula, and retirement income credit.

Ohio starts from federal AGI and applies its own adjustments before applying
the bracket schedule. Supports single and MFJ filing statuses.
"""

from dataclasses import dataclass
from decimal import Decimal

from services.common import round_rate, round_tax
from services.data_loader import load_ohio_data


@dataclass
class OhioTaxResult:
    ohio_agi: Decimal
    personal_exemption: Decimal
    medical_deduction: Decimal
    ohio_tax_base: Decimal
    tax_before_credits: Decimal
    retirement_income_credit: Decimal
    ohio_tax: Decimal
    effective_rate: Decimal


def _compute_ohio_agi(federal_agi: Decimal, ss_taxable_federal: Decimal) -> Decimal:
    """Deduct taxable Social Security from federal AGI to arrive at Ohio AGI."""
    return federal_agi - ss_taxable_federal


def _lookup_personal_exemption(ohio_agi: Decimal, tiers: list[dict]) -> Decimal:
    """Return the personal exemption for the Ohio AGI tier."""
    for tier in tiers:
        agi_up_to = tier["agi_up_to"]
        if agi_up_to is None or ohio_agi <= Decimal(agi_up_to):
            return Decimal(tier["amount"])
    return Decimal(tiers[-1]["amount"])  # pragma: no cover — null sentinel always matches


def _compute_medical_deduction(
    ohio_agi: Decimal, gross_medical: Decimal, floor_rate: Decimal
) -> Decimal:
    """Return the allowable medical deduction after applying the 7.5% AGI floor."""
    medical_floor = round_tax(ohio_agi * floor_rate)
    return max(Decimal("0"), gross_medical - medical_floor)


def _compute_ohio_tax_base(
    ohio_agi: Decimal, personal_exemption: Decimal, medical_deduction: Decimal
) -> Decimal:
    """Return Ohio taxable income after exemption and medical deduction."""
    return max(Decimal("0"), ohio_agi - personal_exemption - medical_deduction)


def _apply_ohio_brackets(ohio_tax_base: Decimal, brackets: list[dict]) -> Decimal:
    """Apply Ohio's cumulative bracket formula to return tax before credits."""
    for bracket in reversed(brackets):
        b_from = Decimal(bracket["from"])
        if ohio_tax_base > b_from:
            base = Decimal(bracket["base"])
            rate = Decimal(bracket["rate"])
            excess_over = Decimal(bracket["excess_over"])
            return round_tax(base + rate * (ohio_tax_base - excess_over))
    return Decimal("0")


def _is_retirement_credit_eligible(
    ohio_agi: Decimal, personal_exemption: Decimal, magi_threshold: Decimal
) -> bool:
    """Return True if MAGI less personal exemption is below the $100,000 threshold."""
    return (ohio_agi - personal_exemption) < magi_threshold


def _lookup_retirement_income_credit(qualifying_income: Decimal, tiers: list[dict]) -> Decimal:
    """Return the retirement income credit for the given qualifying income amount."""
    for tier in tiers:
        income_up_to = tier["income_up_to"]
        if income_up_to is None or qualifying_income <= Decimal(income_up_to):
            return Decimal(tier["credit"])
    return Decimal(tiers[-1]["credit"])  # pragma: no cover — null sentinel always matches


def _compute_effective_rate(ohio_tax: Decimal, ohio_agi: Decimal) -> Decimal:
    """Return effective rate as ohio_tax / ohio_agi, rounded to 4 decimal places."""
    if ohio_agi == Decimal("0"):
        return Decimal("0")
    return round_rate(ohio_tax / ohio_agi)


def calculate_ohio_tax(
    federal_agi: Decimal,
    gross_medical_expenses: Decimal,
    qualifying_retirement_income: Decimal,
    ss_taxable_federal: Decimal,
    tax_year: int,
    filing_status: str = "single",
) -> OhioTaxResult:
    if filing_status not in ("single", "mfj"):
        raise ValueError(f"Unsupported filing status: {filing_status!r}")

    data = load_ohio_data(tax_year)

    ohio_agi = _compute_ohio_agi(federal_agi, ss_taxable_federal)
    exemption_key = (
        "personal_exemption_mfj" if filing_status == "mfj" else "personal_exemption_single"
    )
    personal_exemption = _lookup_personal_exemption(ohio_agi, data[exemption_key])
    medical_deduction = _compute_medical_deduction(
        ohio_agi, gross_medical_expenses, Decimal(data["medical_expense_floor_rate"])
    )
    ohio_tax_base = _compute_ohio_tax_base(ohio_agi, personal_exemption, medical_deduction)
    tax_before_credits = _apply_ohio_brackets(ohio_tax_base, data["brackets"])

    magi_threshold = Decimal(data["magi_credit_threshold"])
    if _is_retirement_credit_eligible(ohio_agi, personal_exemption, magi_threshold):
        retirement_income_credit = _lookup_retirement_income_credit(
            qualifying_retirement_income, data["retirement_income_credit"]
        )
    else:
        retirement_income_credit = Decimal("0")

    ohio_tax = max(Decimal("0"), tax_before_credits - retirement_income_credit)
    effective_rate = _compute_effective_rate(ohio_tax, ohio_agi)

    return OhioTaxResult(
        ohio_agi=ohio_agi,
        personal_exemption=personal_exemption,
        medical_deduction=medical_deduction,
        ohio_tax_base=ohio_tax_base,
        tax_before_credits=tax_before_credits,
        retirement_income_credit=retirement_income_credit,
        ohio_tax=ohio_tax,
        effective_rate=effective_rate,
    )
