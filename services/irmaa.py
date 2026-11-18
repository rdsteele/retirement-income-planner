"""IRMAA: the Medicare Part B and Part D income-related surcharge.

The surcharge is a step function of MAGI. It applies to income two years before the
premium year, so the thresholds that will apply are projected from the planning year's by
a yearly growth rate. Amounts are per person per month in data/irmaa/irmaa_{year}.json,
tier thresholds in data/brackets/federal_{year}.json. Pure Python with no knowledge of the
API layer.
"""

from decimal import ROUND_HALF_UP, Decimal

from services.data_loader import (
    filer_count,
    get_irmaa_lookback_years,
    load_federal_data,
    load_irmaa_data,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_MONTHS = Decimal("12")


def _irmaa_thresholds(filing_status: str, tax_year: int) -> list[Decimal]:
    """The year's published thresholds, lowest first."""
    return [Decimal(t) for t in load_federal_data(tax_year)["irmaa_thresholds"][filing_status]]


def _round_to_unit(amount: Decimal, unit: Decimal) -> Decimal:
    """Round to the nearest multiple of ``unit``."""
    return (amount / unit).quantize(_ONE, rounding=ROUND_HALF_UP) * unit


def _grow_threshold(threshold: Decimal, factor: Decimal, unit: Decimal) -> Decimal:
    return _round_to_unit(threshold * factor, unit)


def projected_thresholds(
    filing_status: str, tax_year: int, inflation_rate: Decimal
) -> list[Decimal]:
    """Thresholds that will apply to this year's income, grown over the lookback.

    Each indexed threshold grows at ``inflation_rate`` a year over the lookback and is
    rounded to the data file's unit. The top threshold stays put when the file says it is
    not indexed. A rate of zero returns the published thresholds.
    """
    thresholds = _irmaa_thresholds(filing_status, tax_year)
    data = load_irmaa_data(tax_year)
    factor = (_ONE + inflation_rate) ** get_irmaa_lookback_years()
    unit = Decimal(data["threshold_rounding"])
    indexed = thresholds if data["index_top_threshold"] else thresholds[:-1]
    grown = [_grow_threshold(t, factor, unit) for t in indexed]
    return grown + thresholds[len(indexed) :]


def _exceeds(magi: Decimal, threshold: Decimal, is_top: bool) -> bool:
    """Whether MAGI reaches this tier: above the threshold, or at it for the top tier."""
    return magi >= threshold if is_top else magi > threshold


def irmaa_tier(magi: Decimal, thresholds: list[Decimal]) -> int:
    """The surcharge tier for MAGI: 0 for none, up to the number of thresholds.

    A tier starts above its threshold; the top tier starts at its threshold.
    """
    last = len(thresholds) - 1
    return sum(1 for i, t in enumerate(thresholds) if _exceeds(magi, t, i == last))


def monthly_surcharge_per_person(tier: int, tax_year: int) -> Decimal:
    """Part B plus Part D monthly surcharge for one person at this tier."""
    if tier == 0:
        return _ZERO
    amounts = load_irmaa_data(tax_year)["monthly_surcharge"]
    return sum((Decimal(amounts[part][tier - 1]) for part in amounts), _ZERO)


def default_enrollees(filing_status: str) -> int:
    """Everyone on the return, unless told otherwise."""
    return filer_count(filing_status)


def _require_valid_enrollees(enrollees: int, filing_status: str) -> None:
    if not 0 <= enrollees <= filer_count(filing_status):
        raise ValueError(f"enrollees must be between 0 and {filer_count(filing_status)}")


def annual_surcharge(
    magi: Decimal,
    *,
    filing_status: str,
    tax_year: int,
    enrollees: int,
    inflation_rate: Decimal,
) -> Decimal:
    """The year's total Part B and Part D surcharge for the household at this MAGI."""
    _require_valid_enrollees(enrollees, filing_status)
    thresholds = projected_thresholds(filing_status, tax_year, inflation_rate)
    monthly = monthly_surcharge_per_person(irmaa_tier(magi, thresholds), tax_year)
    return monthly * _MONTHS * enrollees
