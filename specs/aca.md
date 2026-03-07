# ACA Subsidy Service Specification

## Purpose

Calculate ACA premium tax credit (APTC) at any MAGI level for a single tax year,
returning subsidy amount, subsidy loss, and cliff proximity. Used by the total cost
EMR calculation to show the true marginal cost of each dollar of income including
ACA subsidy loss.

## Background

For 2026 coverage, the enhanced ARP/IRA subsidies expired December 31, 2025.
The original ACA rules returned: premium tax credits are available only to
households with MAGI between 100% and 400% of the prior year FPL. Crossing
400% FPL by $1 eliminates the entire APTC — a hard cliff with no phase-out.

For 2026 coverage, the applicable FPL is the 2025 FPL (one-year lag).
Single person: 400% FPL = $62,600.

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
  "applicable_percentage_400pct": "0.0996"
}
```

**Note:** The SLCSP premium and actual APTC are user inputs, not stored in
config — they vary by age, zip code, and plan. The user knows their exact
APTC from their marketplace enrollment confirmation.

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
    subsidy_loss: Decimal            # subsidy lost vs maximum (at MAGI=0)
    cliff_magi: Decimal              # 400% FPL cliff for this filing status
    distance_to_cliff: Decimal       # cliff_magi - magi (negative if over)
    is_eligible: bool                # True if magi < cliff_magi
    marginal_subsidy_loss: Decimal   # subsidy lost per $1 of additional income
                                     # (0 below cliff, full APTC/1 at cliff)

def calculate_aca_subsidy(
    magi: Decimal,
    slcsp_annual_premium: Decimal,   # Second Lowest Cost Silver Plan annual premium
    filing_status: str,              # "single" or "mfj"
    tax_year: int,
) -> ACAResult:
    ...
```

## Calculation Rules

### 1. Cliff Determination
```
cliff_magi = fpl_100pct[filing_status] × 4.0
```
For 2026 single: `$15,650 × 4 = $62,600`

### 2. APTC Calculation
```
if magi >= cliff_magi:
    aptc_annual = 0
    is_eligible = False
else:
    required_contribution = min(magi × applicable_percentage_400pct, slcsp_annual_premium)
    aptc_annual = max(0, slcsp_annual_premium - required_contribution)
    is_eligible = True
```

**Important:** The applicable percentage at 400% FPL is 9.96% for 2026. At lower
income levels the percentage is lower (sliding scale), meaning the subsidy is
higher. Since the service is primarily used near the cliff for planning purposes,
we use the 9.96% cap as the contribution percentage. For precise subsidy at
lower income levels, use the full sliding scale table from IRS Form 8962.

**Simplification for planning use:** The user's actual APTC from their marketplace
enrollment is more accurate than computing from the sliding scale. The service
supports passing `known_aptc_annual` as an override:

```python
def calculate_aca_subsidy(
    magi: Decimal,
    slcsp_annual_premium: Decimal,
    filing_status: str,
    tax_year: int,
    known_aptc_annual: Decimal | None = None,  # from marketplace enrollment
) -> ACAResult:
```

When `known_aptc_annual` is provided and `magi < cliff_magi`:
- Use `known_aptc_annual` directly as `aptc_annual`
- `subsidy_loss = 0` (at the income level where APTC was calculated)

When `magi >= cliff_magi`:
- `aptc_annual = 0`
- `subsidy_loss = known_aptc_annual` (full subsidy lost)

### 3. Subsidy Loss
```
subsidy_loss = max_aptc - aptc_annual
```
Where `max_aptc` is the APTC at the user's planning income level (not at MAGI=0).

### 4. Marginal Subsidy Loss
The ACA cliff is a step function:
```
if magi < cliff_magi:
    marginal_subsidy_loss = 0      # subsidy unchanged below cliff
elif magi == cliff_magi:
    marginal_subsidy_loss = known_aptc_annual  # full loss at cliff crossing
else:
    marginal_subsidy_loss = 0      # already lost, no further loss
```

This is what creates the EMR spike at the cliff — the entire annual APTC
is lost in a single $1 step.

### 5. Distance to Cliff
```
distance_to_cliff = cliff_magi - magi
```
Positive = dollars remaining before cliff. Negative = dollars over cliff.

## ACA MAGI Definition

ACA MAGI = Federal AGI + tax-exempt interest + untaxed Social Security benefits

For most retirees this equals federal AGI. Key items:
- HSA contributions: **reduce** ACA MAGI (above-the-line deduction) ✅
- Roth IRA withdrawals: **do not** count toward ACA MAGI ✅
- Traditional IRA/Roth conversions: **count** toward ACA MAGI
- LTCG and qualified dividends: **count** toward ACA MAGI
- Return of basis from taxable accounts: **does not** count toward ACA MAGI

The `above_the_line_adjustments` field in the EMR service (HSA contributions)
correctly reduces ACA MAGI — no separate calculation needed.

## Integration with EMR Service

The ACA service is called from the total cost EMR calculation, not directly
from the standalone EMR service. The total cost layer:

1. Calls `calculate_emr()` for tax EMR at each sweep point
2. Calls `calculate_aca_subsidy()` at each sweep point to get subsidy loss
3. Combines: `total_cost_emr = tax_emr + aca_marginal_loss_rate`

The ACA cliff appears as a spike on the total cost EMR chart — potentially
100%+ EMR at the cliff crossing point (full annual subsidy / $1 step).

## Boundary Point Insertion

The ACA cliff must be inserted as an exact boundary point in the sweep,
identical to how Ohio MAGI credit threshold and SS torpedo boundaries
are handled. The cliff MAGI maps to a sweep_value via:

```
sweep_value_at_cliff = cliff_magi - fixed_ordinary - above_the_line_adjustments
                       + standard_deduction + additional_deductions
                       - ss_taxable_at_cliff
```

This ensures the cliff spike appears at the exact correct x-coordinate
rather than being smeared across a $1,000 compute window.

## Worked Example — 2026 Single Filer

Inputs:
- MAGI at planning income: $62,072 (from spreadsheet)
- SLCSP annual premium: $6,480 ($540/month)
- Known APTC: $6,240 ($520/month)
- Cliff MAGI: $62,600

Results at $62,072:
- `aptc_annual`: $6,240
- `subsidy_loss`: $0 (at planning income)
- `distance_to_cliff`: $528
- `is_eligible`: True
- `marginal_subsidy_loss`: $0

Results at $62,601 (one dollar over cliff):
- `aptc_annual`: $0
- `subsidy_loss`: $6,240
- `distance_to_cliff`: -$1
- `is_eligible`: False
- `marginal_subsidy_loss`: $6,240

**EMR impact at cliff crossing:** $6,240 lost in one step.
Over a $1,000 compute window straddling the cliff:
`aca_emr_contribution = $6,240 / $1,000 = 6.24 = 624%`

This will spike above the 50% y-axis cap — the cap should be raised or
the ACA cliff handled separately as an annotation rather than a stacked
area component.

## No Standalone Service for SS Subsidy Interaction

SS benefits count toward ACA MAGI (50% of SS benefit regardless of taxability).
This is already handled correctly in the EMR service provisional income
calculation — no separate treatment needed in the ACA service.

## Data File

`data/aca/aca_2026.json` — created as part of this spec.
`data/aca/aca_2025.json` — not needed (enhanced subsidies, no cliff).

## Tests

Unit tests in `tests/unit/test_aca.py`:
1. Below cliff: returns correct APTC, zero subsidy loss, positive distance
2. At cliff (exact): returns correct APTC, zero subsidy loss, distance=0
3. One dollar over cliff: returns zero APTC, full subsidy loss, distance=-1
4. Known APTC override: uses provided value, not formula calculation
5. Distance to cliff calculation accuracy
6. MFJ cliff uses correct threshold

