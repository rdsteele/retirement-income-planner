"""Income inputs shared by every tax and planning calculation.

One value object carries the forced income and adjustments that EMR, total cost, tax
detail, and the income plan all start from, with the sums they each need. Adding an
income field means adding it here (and to the API models), not to a dozen signatures.
Pure Python with no knowledge of the API layer.
"""

from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from typing import Any

_ZERO = Decimal("0")


def to_decimal(value: object) -> Decimal:
    """Return a JSON-style number as a Decimal (missing or null is zero)."""
    if value is None:
        return _ZERO
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"Not a number: {value!r}") from None


def _read_field(field_type: object, value: object) -> Decimal | bool:
    """A flag field reads as a bool; every other field is an amount."""
    return bool(value) if field_type is bool else to_decimal(value)


@dataclass(frozen=True)
class IncomeInputs:
    pension: Decimal = _ZERO  # taxable portion of pension and annuity income
    wages: Decimal = _ZERO
    interest: Decimal = _ZERO
    ordinary_dividends: Decimal = _ZERO  # non-qualified dividends
    qualified_dividends: Decimal = _ZERO
    ira_distributions: Decimal = _ZERO  # tax-deferred distributions
    other_investment_ordinary: Decimal = _ZERO  # rental, royalties, short-term gains, ...
    ss_benefit: Decimal = _ZERO  # gross benefit; its taxable part is computed
    fixed_ltcg: Decimal = _ZERO
    tax_exempt_interest: Decimal = _ZERO
    above_the_line_adjustments: Decimal = _ZERO
    additional_deductions: Decimal = _ZERO
    taxpayer_65_plus: bool = False  # aged 65 or older by year end (extra standard deduction)
    spouse_65_plus: bool = False  # counts only on a return with two filers
    claim_senior_deduction: bool = False  # the temporary senior deduction for those filers

    @property
    def fixed_ordinary(self) -> Decimal:
        """All ordinary income before taxable Social Security."""
        return (
            self.pension
            + self.wages
            + self.interest
            + self.ordinary_dividends
            + self.ira_distributions
            + self.other_investment_ordinary
        )

    @property
    def investment_ordinary(self) -> Decimal:
        """Ordinary income that is also net investment income."""
        return self.interest + self.ordinary_dividends + self.other_investment_ordinary

    @property
    def fixed_preferential(self) -> Decimal:
        """Qualified dividends plus long-term gains."""
        return self.qualified_dividends + self.fixed_ltcg

    @property
    def net_investment_income(self) -> Decimal:
        """Investment income subject to NIIT: pension, wages, and IRA income are not."""
        return self.investment_ordinary + self.fixed_preferential

    @classmethod
    def from_numbers(cls, values: dict, **overrides: Decimal) -> "IncomeInputs":
        """Build from a mapping of numbers; unknown keys are ignored.

        ``overrides`` replace values from the mapping (for fields stored under another
        name).
        """
        amounts: dict[str, Any] = {
            f.name: _read_field(f.type, values.get(f.name)) for f in fields(cls)
        }
        return cls(**{**amounts, **overrides})
