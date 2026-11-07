"""Additional standard deduction for filers aged 65 or older.

A permanent part of the tax code, indexed each year, so the amounts live in
data/deductions/aged_{year}.json. Kept apart from the rest of the deduction logic so the
rule has one home. Pure Python with no knowledge of the API layer.
"""

from decimal import Decimal

from services.data_loader import filer_count, load_aged_deduction_data
from services.income_inputs import IncomeInputs

_ZERO = Decimal("0")


def aged_filer_count(income: IncomeInputs, filing_status: str) -> int:
    """How many people on the return are 65 or older (a spouse counts only on a joint return)."""
    spouse_counts = income.spouse_65_plus and filer_count(filing_status) > 1
    return int(income.taxpayer_65_plus) + int(spouse_counts)


def additional_standard_deduction(
    income: IncomeInputs, filing_status: str, tax_year: int
) -> Decimal:
    """The extra standard deduction for the filers marked 65 or older (zero if none)."""
    count = aged_filer_count(income, filing_status)
    if count == 0:
        return _ZERO
    per_person = Decimal(
        load_aged_deduction_data(tax_year)["additional_standard_deduction"][filing_status]
    )
    return per_person * count
