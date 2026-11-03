"""Net Investment Income Tax (NIIT) service.

NIIT applies to the lesser of net investment income or the amount by which MAGI
exceeds a filing-status threshold. Only investment income counts; pension, IRA,
and other retirement distributions do not, though they raise MAGI. Standalone
service: thresholds and rate come from the federal data file.
"""

from dataclasses import dataclass
from decimal import Decimal

from services.common import round_tax
from services.data_loader import load_federal_data

_ZERO = Decimal("0")


@dataclass
class NIITResult:
    niit: Decimal
    net_investment_income: Decimal
    threshold: Decimal
    rate: Decimal


def compute_niit(
    magi: Decimal,
    net_investment_income: Decimal,
    threshold: Decimal,
    rate: Decimal,
) -> Decimal:
    """Return NIIT for already-resolved threshold and rate (pure calculation)."""
    if magi <= threshold:
        return _ZERO
    taxable_base = min(net_investment_income, magi - threshold)
    return round_tax(taxable_base * rate)


def load_niit_parameters(filing_status: str, tax_year: int) -> tuple[Decimal, Decimal]:
    """Return (threshold, rate) for the filing status and year from the data file."""
    niit_data = load_federal_data(tax_year)["niit"]
    if filing_status not in niit_data:
        raise ValueError(f"Unsupported filing status: {filing_status!r}")
    return Decimal(niit_data[filing_status]), Decimal(niit_data["rate"])


def calculate_niit(
    magi: Decimal,
    net_investment_income: Decimal,
    filing_status: str,
    tax_year: int,
) -> NIITResult:
    threshold, rate = load_niit_parameters(filing_status, tax_year)
    return NIITResult(
        niit=compute_niit(magi, net_investment_income, threshold, rate),
        net_investment_income=net_investment_income,
        threshold=threshold,
        rate=rate,
    )
