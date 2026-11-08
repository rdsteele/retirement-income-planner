"""Temporary senior deduction for filers aged 65 or older.

Available only for the tax years in data/senior_deduction.json (outside them it is zero),
and reduced by a percentage of income over a threshold. The reduction applies to each
qualifying person's amount, so a couple that both qualify lose the whole deduction at
twice the single filer's phase-out range above the joint threshold (matches the
Retirement Researcher calculator; not checked against the statute's wording). Kept apart from the permanent
age 65+ additional standard deduction (services/aged_deduction.py) so it can be removed
when the provision ends. Pure Python with no knowledge of the API layer.

Which filers are 65 or older comes from the same checkboxes as the additional standard
deduction; ``income.claim_senior_deduction`` is the separate switch for this deduction.
"""

from decimal import Decimal

from services.aged_deduction import aged_filer_count
from services.common import round_tax
from services.data_loader import load_senior_deduction_data
from services.income_inputs import IncomeInputs

_ZERO = Decimal("0")


def senior_deduction_years() -> tuple[int, int]:
    """First and last tax year the deduction is available (from the data file)."""
    data = load_senior_deduction_data()
    return int(data["first_year"]), int(data["last_year"])


def senior_deduction_available(tax_year: int) -> bool:
    first, last = senior_deduction_years()
    return first <= tax_year <= last


def _phaseout_reduction(magi: Decimal, filing_status: str) -> Decimal:
    data = load_senior_deduction_data()
    start = Decimal(data["phaseout_start"][filing_status])
    return Decimal(data["phaseout_rate"]) * max(_ZERO, magi - start)


def senior_deduction(
    income: IncomeInputs, filing_status: str, tax_year: int, magi: Decimal
) -> Decimal:
    """The senior deduction at this MAGI (zero unless claimed, available, and someone is 65+)."""
    count = aged_filer_count(income, filing_status)
    if not income.claim_senior_deduction or count == 0 or not senior_deduction_available(tax_year):
        return _ZERO
    per_person = Decimal(load_senior_deduction_data()["amount_per_person"])
    reduced = max(_ZERO, per_person - _phaseout_reduction(magi, filing_status))
    return round_tax(reduced * count)
