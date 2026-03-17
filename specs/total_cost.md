# Total Cost Service Specification

## Purpose

Combine federal tax, Ohio tax, and ACA subsidy loss into a single total cost
EMR curve. Extends the existing EMR result with ACA components at each sweep
point. Used by the income planning page to show the true marginal cost of each
additional dollar of income.

## Design

`total_cost.py` is a thin orchestration layer — it calls `calculate_emr()` and
`calculate_aca_subsidy()` and combines their results. No sweep logic is
duplicated. All tax calculation remains in `emr.py`.

## Service Interface

```python
# services/total_cost.py

from decimal import Decimal
from dataclasses import dataclass
from services.emr import EMRResult, EMRPoint, SweepMode
from services.aca import ACAResult

@dataclass
class TotalCostPoint:
    # All existing EMRPoint fields (pass-through)
    income: Decimal
    total_tax: Decimal
    emr: Decimal
    emr_ordinary: Decimal
    emr_ss_torpedo: Decimal
    emr_pref_stacking: Decimal
    emr_niit: Decimal
    emr_ohio: Decimal
    ohio_tax: Decimal
    ss_taxable: Decimal
    ss_inclusion_rate: Decimal
    taxable_ordinary: Decimal
    # ACA additions
    aca_magi: Decimal               # ACA MAGI at this sweep point
    aptc_annual: Decimal            # APTC at this sweep point
    aca_subsidy_loss: Decimal       # cumulative subsidy lost vs baseline
    emr_aca: Decimal                # ACA marginal cost component
    # Total
    total_cost_emr: Decimal         # emr + emr_aca

@dataclass
class TotalCostResult:
    points: list[TotalCostPoint]
    # Pass-through from EMRResult
    irmaa_thresholds: list
    tax_year: int
    filing_status: str
    # ACA summary
    aca_cliff_magi: Decimal
    aptc_annual_max: Decimal        # APTC at floor_aca_magi (the ACA MAGI at sweep_floor).
                                    # This is the planning baseline — subsidy available
                                    # at the start of the sweep. If sweep_floor is above
                                    # the lowest schedule point, some subsidy may already
                                    # be lost before the sweep begins.
    cliff_sweep_value: Decimal      # sweep_value where ACA cliff occurs

def calculate_total_cost(
    # All existing calculate_emr() parameters (pass-through)
    pension: Decimal = Decimal('0'),
    interest: Decimal = Decimal('0'),
    ordinary_dividends: Decimal = Decimal('0'),
    ira_distributions: Decimal = Decimal('0'),
    ss_benefit: Decimal = Decimal('0'),
    qualified_dividends: Decimal = Decimal('0'),
    fixed_ltcg: Decimal = Decimal('0'),
    tax_exempt_interest: Decimal = Decimal('0'),
    above_the_line_adjustments: Decimal = Decimal('0'),
    additional_deductions: Decimal = Decimal('0'),
    sweep_mode: SweepMode = SweepMode.ORDINARY,
    variable_ordinary: Decimal = Decimal('0'),
    filing_status: str = 'single',
    tax_year: int = 2026,
    sweep_floor: Decimal = Decimal('0'),
    sweep_ceiling: Decimal | None = None,
    sweep_step: Decimal = Decimal('100'),
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = Decimal('0'),
    ohio_qualifying_retirement_income: Decimal = Decimal('0'),
    # ACA parameters
    include_aca: bool = False,               # False = no ACA overlay
    # APTC amounts are read directly from the ACA schedule in
    # data/aca/aca_{year}.json via calculate_aca_subsidy(). No caller-supplied
    # APTC amount is needed — the schedule provides the full APTC curve.
) -> TotalCostResult:
    ...
```

## Calculation Rules

### 1. Delegate to EMR Service
```python
emr_result = calculate_emr(
    pension=pension,
    interest=interest,
    # ... all pass-through params
    extra_boundary_points=extra_boundary_points,  # ACA cliff + schedule MAGIs
)
```

### 2. ACA MAGI at Each Sweep Point

ACA MAGI is reconstructed from the EMR point fields:

```
aca_magi = (
    fixed_ordinary          # pension + interest + ordinary_dividends + ira_distributions
    + qualified_dividends   # fixed preferential components only
    + fixed_ltcg
    + sweep_value           # variable income being swept
    + ss_taxable            # from EMRPoint.ss_taxable at this point
    - above_the_line_adjustments
    + tax_exempt_interest
)
```

**PREFERENTIAL mode adjustment:** When `sweep_mode = PREFERENTIAL`, `variable_ordinary`
is added into `fixed_ordinary` before the sweep so the formula remains consistent.
`sweep_value` in this case represents variable LTCG, not variable ordinary income.

**Note:** `qualified_dividends + fixed_ltcg` represents the *fixed* preferential
components only. The sweep variable is always captured separately as `sweep_value`,
regardless of mode.

### 3. ACA Subsidy at Each Sweep Point
```python
aca_result = calculate_aca_subsidy(
    magi=aca_magi,
    filing_status=filing_status,
    tax_year=tax_year,
    baseline_magi=floor_aca_magi,   # ACA MAGI at sweep_floor
)
```

### 4. ACA EMR Component
```
emr_aca = aca_result.marginal_subsidy_loss / _EMR_COMPUTE_STEP
```

Where `_EMR_COMPUTE_STEP = 1000` (shared with `emr.py`).
`marginal_subsidy_loss` is expressed as annual APTC dollars lost per $1,000 of
MAGI, so dividing by 1000 gives the EMR rate contribution.

**Note on cliff spike magnitude:** For a $6,240 annual APTC over a $1,000
compute step, `emr_aca = 6.24 = 624%`. This will exceed the y-axis cap.
The frontend handles this via a dedicated ACA cliff annotation rather than
rendering as a stacked area component. See frontend spec.

### 5. Total Cost EMR
```
total_cost_emr = emr + emr_aca
```

### 6. ACA Cliff Boundary Point Insertion
The ACA cliff must be inserted as an exact boundary point. The cliff occurs
when `aca_magi = cliff_magi`. Solve for `sweep_value`:

**ORDINARY mode:**
```
cliff_sweep_value = (
    cliff_magi
    - fixed_ordinary
    - qualified_dividends
    - fixed_ltcg
    - ss_taxable_at_floor        # approximate: use ss_taxable at sweep_floor
    + above_the_line_adjustments
    - tax_exempt_interest
)
```

**PREFERENTIAL mode:** Same formula, but `fixed_ordinary` already includes
`variable_ordinary` (added at the top of `calculate_total_cost()`), so
the formula is consistent across both modes.

**Schedule MAGI boundary injection:** In addition to the cliff boundary point,
all ACA schedule MAGI values (from `get_aptc_schedule_magis()`) that fall within
the sweep range are converted to sweep values using the same formula and injected
as extra boundary points. This ensures the gradual subsidy slope between schedule
points is accurately represented without being smeared across the $1,000 compute
window. Both the cliff and all in-range schedule points are passed together via
`extra_boundary_points` to `calculate_emr()`.

Pass all boundary points to `calculate_emr()` via the `extra_boundary_points`
parameter.

### 7. When include_aca = False
All ACA fields are zero. `total_cost_emr = emr`. Behavior identical to
calling `calculate_emr()` directly.

## Data Flow

```
calculate_total_cost()
    │
    ├── calculate_emr() [floor only, sweep_ceiling=sweep_floor]
    │       → ss_taxable_at_floor, floor_aca_magi
    │
    ├── calculate_aca_subsidy(floor_aca_magi)
    │       → cliff_magi, aptc_annual_max
    │
    ├── compute cliff_sweep_value + schedule boundary points
    │
    ├── calculate_emr() [full sweep, extra_boundary_points injected]
    │       → EMRResult
    │
    └── for each EMRPoint:
            calculate_aca_subsidy(aca_magi, baseline=floor_aca_magi)
            combine → TotalCostPoint

    → TotalCostResult
```

## EMR Service Extension

`calculate_emr()` accepts `extra_boundary_points: list[Decimal] | None = None`.
These are merged with the existing boundary points list before deduplication
and sorting. This allows the total cost layer to inject the ACA cliff and
schedule MAGI boundaries without modifying `emr.py`'s internal boundary logic.

## Worked Example — 2026 Single Filer

Inputs (from spreadsheet):
- pension=$1,596, interest=$3,353, ordinary_dividends=$228
- qualified_dividends=$2,594, fixed_ltcg=$21,819
- above_the_line_adjustments=$5,300, additional_deductions=$23
- ss_benefit=$0, tax_exempt_interest=$0
- include_aca=True
- sweep_mode=ORDINARY, filing_status=single, tax_year=2026

At sweep_value=$38,900 (approximate stacking spike from 2025 analysis):
- aca_magi ≈ $38,900 + $5,177 - $5,323 = $38,754 (well below $62,600 cliff)
- emr_aca = 0 (in gradual slope zone, but small)
- total_cost_emr ≈ emr (tax only)

At cliff crossing (~sweep_value=$59,046):
- aca_magi = $62,600
- emr_aca = $6,240 / $1,000 = 6.24
- total_cost_emr spikes to ~6.36 (624% + ~12% tax rate)

Above cliff:
- emr_aca = 0
- total_cost_emr = emr (tax only, but now paying full premium)

## Tests

`tests/unit/test_total_cost.py`:
1. `include_aca=False` produces identical results to `calculate_emr()`
2. ACA MAGI computed correctly at each sweep point (ORDINARY mode)
3. ACA MAGI computed correctly at each sweep point (PREFERENTIAL mode)
4. `emr_aca=0` below cliff (outside gradual slope), spike at cliff, `0` above cliff
5. `total_cost_emr = emr + emr_aca` at all points
6. Cliff boundary point inserted at correct sweep_value
7. Schedule MAGI boundary points injected within sweep range
8. ORDINARY and PREFERENTIAL modes both compute cliff correctly

`tests/functional/test_total_cost_route.py` — deferred until API route exists.

## No API Route Yet

The total cost service is built and tested standalone. The FastAPI route and
frontend integration come in Phase 3 (income planning page). The service is
the foundation.
