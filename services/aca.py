"""ACA premium tax credit (APTC) calculation service.

Schedule-based calculation for filing statuses with a configured aptc_schedule
(linear interpolation between enrollee-provided healthcare.gov estimates).
Formula fallback for statuses with no schedule (uses applicable_percentage_400pct).

For 2026 coverage: enhanced ARP/IRA subsidies expired; standard 400% FPL hard
cliff applies. Single cliff = $62,600; MFJ cliff = $128,600.
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
_THOUSAND = Decimal("1000")


@dataclass
class ACAResult:
    magi: Decimal                   # input MAGI
    aptc_annual: Decimal            # annual subsidy at this MAGI
    aptc_monthly: Decimal           # monthly subsidy at this MAGI
    subsidy_loss: Decimal           # subsidy lost vs baseline MAGI
    cliff_magi: Decimal             # 400% FPL cliff for this filing status
    distance_to_cliff: Decimal      # cliff_magi - magi (negative if over)
    is_eligible: bool               # True if magi < cliff_magi and above schedule min
    marginal_subsidy_loss: Decimal  # annual APTC dollars lost per $1,000 of additional
                                    # MAGI (consistent with emr_aca = this / 1000 in
                                    # total_cost.py); spikes to full APTC at cliff crossing


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


def _schedule_for(data: dict, filing_status: str) -> list[dict]:
    """Return the aptc_schedule list for the filing status, or []."""
    return data.get("aptc_schedule", {}).get(filing_status, [])


def _interpolate_monthly_aptc(schedule: list[dict], magi: Decimal) -> Decimal:
    """Linear interpolation of monthly APTC from schedule points.

    Returns 0 if magi is below the first schedule point.
    """
    for i, pt in enumerate(schedule):
        pt_magi = Decimal(str(pt["magi"]))
        if magi == pt_magi:
            return Decimal(str(pt["monthly_aptc"]))
        if pt_magi > magi:
            if i == 0:
                return _ZERO  # below lowest schedule point
            lower = schedule[i - 1]
            upper = schedule[i]
            lower_magi = Decimal(str(lower["magi"]))
            upper_magi = Decimal(str(upper["magi"]))
            fraction = (magi - lower_magi) / (upper_magi - lower_magi)
            lower_monthly = Decimal(str(lower["monthly_aptc"]))
            upper_monthly = Decimal(str(upper["monthly_aptc"]))
            return lower_monthly + fraction * (upper_monthly - lower_monthly)
    return _ZERO


def _last_nonzero_annual(schedule: list[dict]) -> Decimal:
    """Return annual APTC at the last schedule point with non-zero monthly APTC."""
    for pt in reversed(schedule):
        monthly = Decimal(str(pt["monthly_aptc"]))
        if monthly > _ZERO:
            return monthly * _TWELVE
    return _ZERO


def _marginal_loss_from_schedule(
    schedule: list[dict],
    magi: Decimal,
    cliff_magi: Decimal,
) -> Decimal:
    """Annual APTC dollars lost per $1,000 of additional MAGI.

    - Below cliff (between schedule points): slope × 1000, matching the
      emr_aca = marginal_subsidy_loss / _EMR_COMPUTE_STEP convention in total_cost.py.
    - At cliff crossing (magi == cliff_magi): full annual APTC at last non-zero
      schedule point (the cliff spike).
    - Above cliff or below schedule minimum: 0.
    - Last interval before cliff (upper bound is the cliff point): 0, because the
      {cliff_magi, 0} schedule entry represents the cliff, not a gradual slope.
    """
    if magi > cliff_magi:
        return _ZERO
    if magi == cliff_magi:
        return _last_nonzero_annual(schedule)
    if not schedule or magi < Decimal(str(schedule[0]["magi"])):
        return _ZERO

    for i in range(len(schedule) - 1):
        lower_magi = Decimal(str(schedule[i]["magi"]))
        upper_magi = Decimal(str(schedule[i + 1]["magi"]))
        if lower_magi <= magi <= upper_magi:
            # Skip interval where upper bound is the cliff point —
            # that represents the cliff, not a gradual subsidy slope.
            if upper_magi >= cliff_magi:
                return _ZERO
            lower_annual = Decimal(str(schedule[i]["monthly_aptc"])) * _TWELVE
            upper_annual = Decimal(str(schedule[i + 1]["monthly_aptc"])) * _TWELVE
            return (lower_annual - upper_annual) / (upper_magi - lower_magi) * _THOUSAND

    return _ZERO


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


def get_aptc_schedule_magis(filing_status: str, tax_year: int) -> list[Decimal]:
    """Return MAGI values from the aptc_schedule (empty list if no schedule)."""
    data = _load_aca_data(tax_year)
    schedule = _schedule_for(data, filing_status)
    return [Decimal(str(pt["magi"])) for pt in schedule]


def calculate_aca_subsidy(
    magi: Decimal,
    filing_status: str,
    tax_year: int,
    baseline_magi: Decimal | None = None,
    slcsp_annual_premium: Decimal = _ZERO,
) -> ACAResult:
    """Calculate ACA subsidy at the given MAGI.

    Args:
        magi: Modified adjusted gross income for ACA purposes.
        filing_status: "single" or "mfj".
        tax_year: Coverage year (determines FPL cliff and schedule).
        baseline_magi: MAGI for subsidy_loss reference. Defaults to the lowest
            schedule point MAGI (schedule-based) or no loss (formula fallback).
        slcsp_annual_premium: Second Lowest Cost Silver Plan annual premium.
            Only used when the schedule is empty (formula fallback).
    """
    data = _load_aca_data(tax_year)

    if filing_status not in ("single", "mfj"):
        raise ValueError(f"Unsupported filing status: {filing_status!r}")

    fpl_100pct = Decimal(str(data["fpl_100pct"][filing_status]))
    cliff_magi = _cliff_from_fpl(fpl_100pct)
    distance_to_cliff = cliff_magi - magi
    schedule = _schedule_for(data, filing_status)

    if schedule:
        min_schedule_magi = Decimal(str(schedule[0]["magi"]))

        if magi >= cliff_magi:
            aptc_annual = _ZERO
            is_eligible = False
        elif magi < min_schedule_magi:
            aptc_annual = _ZERO
            is_eligible = False
        else:
            monthly = _interpolate_monthly_aptc(schedule, magi)
            aptc_annual = round_tax(monthly * _TWELVE)
            is_eligible = True

        effective_baseline = baseline_magi if baseline_magi is not None else min_schedule_magi
        baseline_monthly = _interpolate_monthly_aptc(schedule, effective_baseline)
        baseline_aptc = round_tax(baseline_monthly * _TWELVE)
        subsidy_loss = round_tax(max(_ZERO, baseline_aptc - aptc_annual))
        marginal_subsidy_loss = _marginal_loss_from_schedule(schedule, magi, cliff_magi)
    else:
        # Formula fallback for filing statuses with no schedule
        applicable_percentage = Decimal(data["applicable_percentage_400pct"])
        if magi >= cliff_magi:
            aptc_annual = _ZERO
            is_eligible = False
        else:
            aptc_annual = _formula_aptc(magi, slcsp_annual_premium, applicable_percentage)
            is_eligible = True

        if baseline_magi is not None:
            baseline_aptc = _formula_aptc(baseline_magi, slcsp_annual_premium, applicable_percentage)
        else:
            baseline_aptc = aptc_annual
        subsidy_loss = round_tax(max(_ZERO, baseline_aptc - aptc_annual))

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
