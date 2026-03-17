# ACA Subsidy Service Specification

## Purpose

Calculate ACA premium tax credit (APTC) at any MAGI level for a single tax year,
returning subsidy amount, subsidy loss, and cliff proximity. Used by the total cost
EMR calculation to show the true marginal cost of each dollar of income including
ACA subsidy loss. Also used by the income planning page cost rate curve.

## Background

For 2026 coverage, the enhanced ARP/IRA subsidies expired December 31, 2025.
The original ACA rules returned: premium tax credits are available only to
households with MAGI between 100% and 400% of the prior year FPL. Crossing
400% FPL by $1 eliminates the entire APTC — a hard cliff with no phase-out.

For 2026 coverage, the applicable FPL is the 2025 FPL (one-year lag).
Single person: 400% FPL = $62,600.

The APTC slides downward as MAGI increases below the cliff — it is not flat.
The rate of decline is determined by the IRS applicable percentage table
(Rev. Proc. 2025-25) combined with age-rating factors specific to the enrollee.
Rather than attempting to replicate the full formula, the service uses an
enrollee-provided APTC schedule of actual healthcare.gov estimates at known
MAGI levels. Linear interpolation is used between schedule points.

---

## Configuration

ACA parameters are stored in `data/aca/aca_{year}.json`:

```json
{
  "tax_year": 2026,
  "filing_status_cliffs": {
    "single": 62600,
    "mfj": 128600
  },
  "fpl_100pct": {
    "single": 15650,
    "mfj": 32150
  },
  "applicable_percentage_400pct": "0.0996",
  "aptc_schedule": {
    "single": [
      {"magi": 22000, "monthly_aptc": 972},
      {"magi": 25000, "monthly_aptc": 941},
      {"magi": 30000, "monthly_aptc": 883},
      {"magi": 35000, "monthly_aptc": 820},
      {"magi": 40000, "monthly_aptc": 751},
      {"magi": 45000, "monthly_aptc": 679},
      {"magi": 50000, "monthly_aptc": 623},
      {"magi": 55000, "monthly_aptc": 582},
      {"magi": 60000, "monthly_aptc": 540},
      {"magi": 62500, "monthly_aptc": 520},
      {"magi": 62600, "monthly_aptc": 0}
    ],
    "mfj": []
  }
}
```

**Notes:**
- Schedule points come from actual healthcare.gov APTC estimates for the
  enrollee's specific age, zip code, and plan year. More points = more
  accurate interpolation.
- The schedule must include a point at or just below the cliff MAGI with
  the last non-zero APTC, and a point at the cliff MAGI with `monthly_aptc: 0`.
- Points must be sorted ascending by MAGI.
- Below the lowest schedule MAGI: ineligible (Medicaid territory).
- Above the cliff: `aptc = 0`.
- If `aptc_schedule` is empty for a filing status, the service falls back
  to the formula-based calculation using `applicable_percentage_400pct`.
- Schedule is updated annually by the user from healthcare.gov estimates.

---

## Service Interface

```python
# services/aca.py

from decimal import Decimal
from dataclasses import dataclass

@dataclass
class ACAResult:
    magi: Decimal                    # input MAGI
    aptc_annual: Decimal             # annual subsidy at this MAGI
    aptc_monthly: Decimal            # monthly subsidy at this MAGI
    subsidy_loss: Decimal            # subsidy lost vs baseline MAGI
                                     # (baseline = lowest schedule point)
    cliff_magi: Decimal              # 400% FPL cliff for this filing status
    distance_to_cliff: Decimal       # cliff_magi - magi (negative if over)
    is_eligible: bool                # True if magi < cliff_magi and above
                                     # lowest schedule point
    marginal_subsidy_loss: Decimal   # annual APTC dollars lost per $1,000 of
                                     # additional MAGI (matches _EMR_COMPUTE_STEP
                                     # in total_cost.py so emr_aca = this / 1000);
                                     # spikes to full annual APTC at cliff crossing,
                                     # 0 above cliff or below schedule minimum

def calculate_aca_subsidy(
    magi: Decimal,
    filing_status: str,              # "single" or "mfj"
    tax_year: int,
    baseline_magi: Decimal | None = None,  # MAGI for subsidy_loss reference
                                           # defaults to lowest schedule point
    slcsp_annual_premium: Decimal = Decimal('0'),
                                     # Second Lowest Cost Silver Plan annual premium.
                                     # Only used when aptc_schedule is empty for the
                                     # filing status (formula fallback path).
) -> ACAResult:
    ...
```

---

## Calculation Rules

### 1. Cliff Determination
```
cliff_magi = fpl_100pct[filing_status] × 4.0
```
For 2026 single: `$15,650 × 4 = $62,600`

### 2. APTC from Schedule

If `aptc_schedule` is non-empty for the filing status:

```
if magi >= cliff_magi:
    aptc_annual = 0
    is_eligible = False
elif magi < min(schedule.magi):
    aptc_annual = 0
    is_eligible = False  # Medicaid territory
else:
    aptc_monthly = interpolate(schedule, magi)
    aptc_annual = aptc_monthly * 12
    is_eligible = True
```

**Linear interpolation between adjacent schedule points:**
```
aptc_monthly = lower.monthly_aptc + (
    (magi - lower.magi) / (upper.magi - lower.magi)
    × (upper.monthly_aptc - lower.monthly_aptc)
)
```

If `magi` exactly matches a schedule point, use that point's value directly.

### 3. APTC Formula Fallback

If `aptc_schedule` is empty for the filing status, fall back to the
applicable percentage formula:

```
if magi >= cliff_magi:
    aptc_annual = 0
else:
    applicable_pct = interpolated from applicable percentage table
    required_contribution = magi × applicable_pct
    aptc_annual = max(0, slcsp_annual - required_contribution)
```

This fallback requires `slcsp_annual_premium` as an additional parameter.
It is less accurate than the schedule-based approach for enrollees with
age-rated premiums.

**Note on formula fallback marginal loss:** In the formula fallback path,
`marginal_subsidy_loss` spikes to the full annual APTC at the cliff crossing
and is `0` everywhere else. The gradual slope is not modeled in the fallback
because the applicable percentage formula requires a full SLCSP premium curve
to compute accurately. This is an acceptable simplification since the formula
fallback is only used for filing statuses with no configured schedule (e.g. MFJ
when `aptc_schedule.mfj` is empty).

### 4. Subsidy Loss

```
baseline_aptc = aptc_at(baseline_magi or min(schedule.magi))
subsidy_loss = max(0, baseline_aptc - aptc_annual)
```

Subsidy loss is zero at or below the baseline MAGI and increases as MAGI
rises toward and above the cliff.

### 5. Marginal Subsidy Loss

The marginal subsidy loss at a given MAGI is expressed as annual APTC dollars
lost per $1,000 of additional MAGI, consistent with `_EMR_COMPUTE_STEP = 1000`
in `total_cost.py` (so that `emr_aca = marginal_subsidy_loss / 1000`):

```
# Below cliff — slope between adjacent schedule points (per $1,000 MAGI):
marginal_subsidy_loss = (
    (lower.aptc_annual - upper.aptc_annual) / (upper.magi - lower.magi)
) × 1000

# Exception: last interval before cliff (upper.magi >= cliff_magi) → 0
# because the {cliff_magi, 0} schedule entry represents the cliff drop,
# not a gradual slope to be modeled continuously.

# At cliff crossing (magi == cliff_magi):
marginal_subsidy_loss = aptc_annual_just_below_cliff  # full annual APTC

# Above cliff:
marginal_subsidy_loss = 0  # already lost

# Below schedule minimum:
marginal_subsidy_loss = 0
```

This produces:
- A small positive `emr_aca` component for each $1,000 of income in the
  gradual slope zone (typically 1–3% per $1,000)
- A large spike at the cliff crossing (`emr_aca = full_aptc / 1000`,
  e.g. 624% for a $6,240 annual APTC)

### 6. Distance to Cliff
```
distance_to_cliff = cliff_magi - magi
```
Positive = dollars remaining before cliff. Negative = dollars over cliff.

---

## ACA MAGI Definition

ACA MAGI = Federal AGI + tax-exempt interest + untaxed Social Security benefits

For most retirees this equals federal AGI. Key items:
- HSA contributions: **reduce** ACA MAGI (above-the-line deduction) ✅
- Roth IRA withdrawals: **do not** count toward ACA MAGI ✅
- Traditional IRA/Roth conversions: **count** toward ACA MAGI
- LTCG and qualified dividends: **count** toward ACA MAGI
- Return of basis from taxable accounts: **does not** count toward ACA MAGI

---

## Integration with EMR / Total Cost Service

The ACA service is called from the total cost EMR calculation at each sweep
point. The total cost layer:

1. Calls `calculate_emr()` for tax EMR at each sweep point
2. Calls `calculate_aca_subsidy()` at each sweep point to get subsidy loss
3. Combines: `total_cost_emr = tax_emr + aca_marginal_loss_rate`

The ACA cliff appears as a spike on the total cost EMR chart. Below the cliff,
the gradual subsidy slide also contributes a small positive EMR component at
each point — typically 1-3% per $1,000 of additional income.

## Boundary Point Insertion

The ACA cliff must be inserted as an exact boundary point in the sweep.
The cliff MAGI maps to a sweep_value via:

```
sweep_value_at_cliff = cliff_magi - fixed_ordinary
                       - ss_taxable_at_floor
                       + above_the_line_adjustments
                       - tax_exempt_interest
```

This ensures the cliff spike appears at the exact correct x-coordinate.

All schedule MAGI points that fall within the sweep range should also be
inserted as boundary points to ensure the gradual slope is accurately
represented without being smeared across a $1,000 compute window.

---

## Worked Example — 2026 Single Filer

Inputs:
- MAGI: $35,346 (from income planning)
- Filing status: single
- Tax year: 2026
- Baseline MAGI: $22,000 (lowest schedule point)

Results at $35,346 (interpolated between $35,000 and $40,000):
```
lower = {magi: 35000, monthly_aptc: 820}
upper = {magi: 40000, monthly_aptc: 751}
fraction = (35346 - 35000) / (40000 - 35000) = 0.0692
monthly_aptc = 820 + 0.0692 × (751 - 820) = 820 - 4.77 = 815.23
aptc_annual = 815.23 × 12 = $9,783
baseline_aptc = 972 × 12 = $11,664
subsidy_loss = $11,664 - $9,783 = $1,881
distance_to_cliff = $62,600 - $35,346 = $27,254
is_eligible = True
```

Results at $62,601 (one dollar over cliff):
```
aptc_annual = $0
subsidy_loss = $11,664 (full baseline lost)
distance_to_cliff = -$1
is_eligible = False
```

---

## Data File

`data/aca/aca_2026.json` — updated with `aptc_schedule` as shown above.
`data/aca/aca_2025.json` — not needed (enhanced subsidies, no cliff, no schedule).

---

## Tests

Unit tests in `tests/unit/test_aca.py`:
1. Schedule interpolation — MAGI between two points returns correct value
2. Schedule exact match — MAGI exactly on a schedule point
3. Below lowest schedule point — returns zero APTC, is_eligible=False
4. At cliff — returns last non-zero APTC, distance_to_cliff=0
5. One dollar over cliff — returns zero APTC, full subsidy_loss
6. Subsidy loss correct vs baseline MAGI
7. Marginal subsidy loss correct between schedule points (gradual slope, per $1,000)
8. Marginal subsidy loss spikes at cliff crossing (full annual APTC)
9. Empty schedule falls back to formula calculation
10. MFJ cliff uses correct threshold
