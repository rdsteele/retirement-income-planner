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
    aca_subsidy_loss: Decimal       # cumulative subsidy lost vs max
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
    aptc_annual_max: Decimal        # APTC at sweep_floor (planning baseline)
    cliff_sweep_value: Decimal      # sweep_value where ACA cliff occurs

def calculate_total_cost(
    # All existing calculate_emr() parameters (pass-through)
    pension: Decimal = Decimal('0'),
    interest: Decimal = Decimal('0'),
    ordinary_dividends: Decimal = Decimal('0'),
    inherited_ira_rmd: Decimal = Decimal('0'),
    ss_benefit: Decimal = Decimal('0'),
    qualified_dividends: Decimal = Decimal('0'),
    fixed_ltcg: Decimal = Decimal('0'),
    tax_exempt_interest: Decimal = Decimal('0'),
    above_the_line_adjustments: Decimal = Decimal('0'),
    additional_deductions: Decimal = Decimal('0'),
    sweep_mode: SweepMode = SweepMode.ORDINARY,
    filing_status: str = 'single',
    tax_year: int = 2026,
    sweep_floor: Decimal = Decimal('0'),
    sweep_ceiling: Decimal | None = None,
    sweep_step: Decimal = Decimal('100'),
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = Decimal('0'),
    ohio_qualifying_retirement_income: Decimal = Decimal('0'),
    # ACA parameters
    aptc_monthly: Decimal = Decimal('0'),    # known APTC from marketplace
    include_aca: bool = False,               # False = no ACA overlay
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
)
```

### 2. ACA MAGI at Each Sweep Point
```
aca_magi = agi + tax_exempt_interest
```
Where `agi` is already computed inside the EMR service at each point.
Since we can't access the internal AGI directly, reconstruct it:

```
aca_magi = (
    fixed_ordinary
    + sweep_value                      # variable ordinary (ORDINARY mode)
    + ss_taxable                       # from EMRPoint.ss_taxable
    + total_preferential               # fixed + sweep (PREFERENTIAL mode)
    - above_the_line_adjustments
    + tax_exempt_interest
)
```

Where `fixed_ordinary = pension + interest + ordinary_dividends + inherited_ira_rmd`
and `total_preferential = qualified_dividends + fixed_ltcg` (ORDINARY mode)
or `qualified_dividends + fixed_ltcg + sweep_value` (PREFERENTIAL mode).

### 3. ACA Subsidy at Each Sweep Point
```python
aca_result = calculate_aca_subsidy(
    magi=aca_magi,
    slcsp_annual_premium=Decimal('0'),   # not needed when known_aptc provided
    filing_status=filing_status,
    tax_year=tax_year,
    known_aptc_annual=aptc_monthly * 12,
)
```

### 4. ACA EMR Component
The ACA contribution to EMR is a step function at the cliff:
```
emr_aca = aca_result.marginal_subsidy_loss / _EMR_COMPUTE_STEP
```

Where `_EMR_COMPUTE_STEP` matches the value used in `emr.py` (currently $1,000).
This produces `emr_aca = known_aptc_annual / 1000` at the cliff crossing point
and `0` everywhere else.

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
    - ss_taxable_at_cliff        # approximate: use ss_taxable at sweep_floor
    + above_the_line_adjustments
    - tax_exempt_interest
)
```

**PREFERENTIAL mode:**
```
cliff_sweep_value = (
    cliff_magi
    - fixed_ordinary
    - ss_taxable_at_floor
    + above_the_line_adjustments
    - tax_exempt_interest
    - fixed_ltcg
    - qualified_dividends
)
```

Pass `cliff_sweep_value` as an additional boundary point to `calculate_emr()`
via a new optional parameter `extra_boundary_points: list[Decimal] | None`.

### 7. When include_aca = False
All ACA fields are zero. `total_cost_emr = emr`. Behavior identical to
calling `calculate_emr()` directly.

## Data Flow

```
calculate_total_cost()
    │
    ├── calculate_emr()          → EMRResult (tax sweep with boundaries)
    │                                        
    └── for each EMRPoint:
            calculate_aca_subsidy()  → ACAResult
            combine → TotalCostPoint
    
    → TotalCostResult
```

## EMR Service Extension

Add `extra_boundary_points: list[Decimal] | None = None` parameter to
`calculate_emr()`. These are merged with the existing boundary points list
before deduplication and sorting. This allows the total cost layer to inject
the ACA cliff boundary without modifying `emr.py`'s internal boundary logic.

## Worked Example — 2026 Single Filer

Inputs (from spreadsheet):
- pension=$1,596, interest=$3,353, ordinary_dividends=$228
- qualified_dividends=$2,594, fixed_ltcg=$21,819
- above_the_line_adjustments=$5,300, additional_deductions=$23
- ss_benefit=$0, tax_exempt_interest=$0
- aptc_monthly=$520, include_aca=True
- sweep_mode=ORDINARY, filing_status=single, tax_year=2026

At sweep_value=$38,900 (approximate stacking spike from 2025 analysis):
- aca_magi ≈ $38,900 + $5,177 - $5,323 = $38,754 (well below $62,600 cliff)
- emr_aca = 0
- total_cost_emr = emr (tax only)

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
2. ACA MAGI computed correctly at each sweep point
3. `emr_aca=0` below cliff, spike at cliff, `0` above cliff
4. `total_cost_emr = emr + emr_aca` at all points
5. Cliff boundary point inserted at correct sweep_value
6. ORDINARY and PREFERENTIAL modes both compute cliff correctly

`tests/functional/test_total_cost_route.py` — deferred until API route exists.

## No API Route Yet

The total cost service is built and tested standalone. The FastAPI route and
frontend integration come in Phase 3 (income planning page). The service is
the foundation.

