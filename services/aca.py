"""ACA premium tax credit (APTC) calculation service.

Determines the annual subsidy, subsidy loss, and cliff proximity for a given
MAGI level. Handles the 400% FPL hard cliff for 2026 coverage: crossing by $1
eliminates the entire APTC — a step function with no phase-out.

For 2026, the enhanced ARP/IRA subsidies expired. Standard ACA rules apply:
subsidies are available only to households with MAGI at or below 400% FPL.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from services.common import round_tax

_DATA_DIR = Path(__file__).parent.parent / "data" / "aca"
_ZERO = Decimal("0")
_FOUR = Decimal("4")
_TWELVE = Decimal("12")


@dataclass
class ACAResult:
    magi: Decimal                   # input MAGI
    aptc_annual: Decimal            # annual subsidy at this MAGI
    aptc_monthly: Decimal           # monthly subsidy at this MAGI
    subsidy_loss: Decimal           # subsidy lost vs baseline (0 below cliff)
    cliff_magi: Decimal             # 400% FPL cliff for this filing status
    distance_to_cliff: Decimal      # cliff_magi - magi (negative if over)
    is_eligible: bool               # True if magi <= cliff_magi
    marginal_subsidy_loss: Decimal  # full APTC at exact cliff, 0 everywhere else


@lru_cache(maxsize=None)
def _load_aca_data(tax_year: int) -> dict:
    path = _DATA_DIR / f"aca_{tax_year}.json"
    if not path.exists():
        raise ValueError(f"Unsupported tax year: {tax_year}")
    with path.open() as f:
        return json.load(f)


def _cliff_from_fpl(fpl_100pct: Decimal) -> Decimal:
    """Return the 400% FPL cliff MAGI."""
    return fpl_100pct * _FOUR


def _formula_aptc(
    magi: Decimal,
    slcsp_annual_premium: Decimal,
    applicable_percentage: Decimal,
) -> Decimal:
    """Return annual APTC using the applicable-percentage formula."""
    required_contribution = min(
        round_tax(magi * applicable_percentage),
        slcsp_annual_premium,
    )
    return round_tax(max(_ZERO, slcsp_annual_premium - required_contribution))


def calculate_aca_subsidy(
    magi: Decimal,
    slcsp_annual_premium: Decimal,
    filing_status: str,
    tax_year: int,
    known_aptc_annual: Decimal | None = None,
) -> ACAResult:
    """Calculate ACA subsidy at the given MAGI.

    Args:
        magi: Modified adjusted gross income for ACA purposes.
        slcsp_annual_premium: Second Lowest Cost Silver Plan annual premium.
        filing_status: "single" or "mfj".
        tax_year: Coverage year (determines FPL cliff).
        known_aptc_annual: Actual APTC from marketplace enrollment, if known.
            When provided and MAGI is below the cliff, used directly instead of
            the formula — more accurate for planning near the cliff.
    """
    data = _load_aca_data(tax_year)

    if filing_status not in ("single", "mfj"):
        raise ValueError(f"Unsupported filing status: {filing_status!r}")

    fpl_100pct = Decimal(str(data["fpl_100pct"][filing_status]))
    cliff_magi = _cliff_from_fpl(fpl_100pct)
    applicable_percentage = Decimal(data["applicable_percentage_400pct"])

    distance_to_cliff = cliff_magi - magi
    # At or below 400% FPL: eligible. Strictly above: cliff applies.
    is_eligible = magi <= cliff_magi

    if known_aptc_annual is not None:
        if is_eligible:
            aptc_annual = known_aptc_annual
            subsidy_loss = _ZERO
        else:
            aptc_annual = _ZERO
            subsidy_loss = known_aptc_annual
        # Marginal loss is the full APTC only at the exact cliff crossing point.
        # One more dollar above cliff_magi loses everything; below it loses nothing.
        marginal_subsidy_loss = known_aptc_annual if magi == cliff_magi else _ZERO
    else:
        if is_eligible:
            aptc_annual = _formula_aptc(magi, slcsp_annual_premium, applicable_percentage)
            subsidy_loss = _ZERO
        else:
            aptc_annual = _ZERO
            cliff_aptc = _formula_aptc(cliff_magi, slcsp_annual_premium, applicable_percentage)
            subsidy_loss = cliff_aptc
        cliff_aptc = _formula_aptc(cliff_magi, slcsp_annual_premium, applicable_percentage)
        marginal_subsidy_loss = cliff_aptc if magi == cliff_magi else _ZERO

    aptc_monthly = round_tax(aptc_annual / _TWELVE)

    return ACAResult(
        magi=magi,
        aptc_annual=aptc_annual,
        aptc_monthly=aptc_monthly,
        subsidy_loss=subsidy_loss,
        cliff_magi=cliff_magi,
        distance_to_cliff=distance_to_cliff,
        is_eligible=is_eligible,
        marginal_subsidy_loss=marginal_subsidy_loss,
    )
