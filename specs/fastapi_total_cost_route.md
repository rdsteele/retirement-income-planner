# Spec: FastAPI Total Cost Route

**Version:** 1.0
**Status:** Draft
**Covers:** `api/routers/total_cost.py`, `api/models/total_cost.py`

---

## Purpose

Expose the `calculate_total_cost` service as an HTTP endpoint. The route is a thin
wrapper — it deserializes the request, calls the service, converts the result to a
frontend-friendly JSON shape, and handles errors. No business logic lives here.

This route is the primary endpoint consumed by the income planning page to render
the total cost EMR chart and key points table.

---

## Architecture Rules

- Routes import from `services/` — never the reverse
- All validation that protects service correctness lives in the service layer
- The route catches `ValueError` from services and returns structured 422 responses
- `Decimal` is used inside services. The route converts all `Decimal` values to
  `float` at the API boundary before returning JSON
- Pydantic models are used for request deserialization and response serialization
- No tax logic, no bracket data, no rounding in route code

---

## Endpoint

```
POST /api/total-cost
Content-Type: application/json
```

---

## Request Model

Pydantic model `TotalCostRequest` in `api/models/total_cost.py`.

All monetary fields are `float`, non-negative. The route converts them to
`Decimal` before passing to the service.

### Fixed Income Fields (all optional, default `0.0`)

| Field | Type | Description |
|---|---|---|
| `pension` | `float` | Fixed pension or annuity income |
| `interest` | `float` | Taxable interest income |
| `ordinary_dividends` | `float` | Non-qualified dividends |
| `inherited_ira_rmd` | `float` | Required minimum distributions |
| `ss_benefit` | `float` | Gross Social Security benefit |
| `qualified_dividends` | `float` | Qualified dividends (preferential rate) |
| `fixed_ltcg` | `float` | Fixed LTCG already realized |
| `tax_exempt_interest` | `float` | Tax-exempt interest income |
| `above_the_line_adjustments` | `float` | HSA contributions, IRA deductions, etc. |
| `additional_deductions` | `float` | QBI, excess itemized deductions, etc. |

### Mode and Sweep Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `sweep_mode` | `str` | required | `"ordinary"` or `"preferential"` |
| `variable_ordinary` | `float` | `0.0` | Fixed IRA/Roth amount in PREFERENTIAL mode |
| `sweep_floor` | `float` | `0.0` | Start of sweep range |
| `sweep_ceiling` | `float` | `null` | End of sweep range (null = default) |
| `sweep_step` | `float` | `100.0` | Increment between sweep points |
| `filing_status` | `str` | required | `"single"` or `"mfj"` |
| `tax_year` | `int` | required | e.g. `2026` |

### Ohio Fields (all optional)

| Field | Type | Default | Description |
|---|---|---|---|
| `include_ohio` | `bool` | `false` | Include Ohio tax in EMR calculation |
| `ohio_medical_deduction` | `float` | `0.0` | Pre-computed Ohio medical deduction |
| `ohio_qualifying_retirement_income` | `float` | `0.0` | IRA + pension qualifying for retirement credit |

### ACA Fields (all optional)

| Field | Type | Default | Description |
|---|---|---|---|
| `include_aca` | `bool` | `false` | Include ACA subsidy loss in total cost |
| `aptc_monthly` | `float` | `0.0` | Known monthly APTC from marketplace enrollment |
| `silver_premium_monthly` | `float` | `0.0` | Monthly SLCSP premium (used if no known APTC) |

### Request Validation (Pydantic)

- All monetary fields: `ge=0`
- `sweep_mode`: must be `"ordinary"` or `"preferential"`
- `filing_status`: must be `"single"` or `"mfj"`
- `tax_year`: positive integer
- `sweep_step`: `gt=0`
- `sweep_floor`: `ge=0`
- `sweep_ceiling`: `gt=0` if provided

---

## Response Model

Returns HTTP 200 with `TotalCostResponse` JSON body.

All numeric values are `float`. No `Decimal`, no Python-specific types.

```json
{
  "sweep_mode": "ordinary",
  "filing_status": "single",
  "tax_year": 2026,
  "points": {
    "income":             [0.0, 100.0, 200.0],
    "total_tax":          [700.0, 712.0, 724.0],
    "emr":                [0.10, 0.10, 0.12],
    "components": {
      "ordinary":         [0.10, 0.10, 0.12],
      "ss_torpedo":       [0.0,  0.0,  0.0],
      "pref_stacking":    [0.0,  0.0,  0.0],
      "niit":             [0.0,  0.0,  0.0],
      "ohio":             [0.0,  0.0,  0.0],
      "aca":              [0.0,  0.0,  0.0]
    },
    "ss_taxable":         [0.0, 0.0, 0.0],
    "ss_inclusion_rate":  [0.0, 0.0, 0.0],
    "taxable_ordinary":   [7000.0, 7100.0, 7200.0],
    "ohio_tax":           [0.0, 0.0, 0.0],
    "aca_magi":           [0.0, 100.0, 200.0],
    "aptc_annual":        [6240.0, 6240.0, 6240.0],
    "aca_subsidy_loss":   [0.0, 0.0, 0.0],
    "total_cost_emr":     [0.10, 0.10, 0.12]
  },
  "irmaa_thresholds": [106000.0, 133000.0, 167000.0, 200000.0, 500000.0],
  "aca_cliff_magi": 62600.0,
  "aptc_annual_max": 6240.0,
  "cliff_sweep_value": 59046.0,
  "planning_signals": {
    "zero_rate_threshold":   15750.0,
    "aca_cliff_sweep_value": 59046.0,
    "bracket_boundaries": [
      {"sweep_value": 0.0,     "rate": 0.10, "notes": "10% bracket"},
      {"sweep_value": 12225.0, "rate": 0.12, "notes": "12% bracket"},
      {"sweep_value": 47150.0, "rate": 0.22, "notes": "22% bracket"}
    ],
    "ltcg_0pct_remaining":  26350.0,
    "torpedo_active":       false,
    "ss_fully_taxable":     false,
    "distance_to_22pct":    19350.0,
    "distance_to_24pct":    null
  }
}
```

### Points Arrays

Parallel arrays — all arrays have the same length, one entry per sweep point.
The `aca` component array is all zeros when `include_aca = false`.

### Planning Signals

Derived from the points array by the route after the service returns.

| Signal | Type | Description |
|---|---|---|
| `zero_rate_threshold` | `float \| null` | Sweep value where `emr_ordinary` first becomes > 0 (standard deduction exhausted) |
| `aca_cliff_sweep_value` | `float \| null` | Sweep value where `aca_subsidy_loss` first becomes > 0. `null` if `include_aca = false` |
| `bracket_boundaries` | `list` | Each entry where `emr_ordinary` changes: `{sweep_value, rate, notes}` |
| `ltcg_0pct_remaining` | `float \| null` | Income remaining before LTCG enters 15% bracket. `null` if already past threshold or sweep_mode is ORDINARY with no preferential income |
| `torpedo_active` | `bool` | True if any point has `emr_ss_torpedo > 0` |
| `ss_fully_taxable` | `bool` | True if SS inclusion rate has reached 85% at `sweep_floor` |
| `distance_to_22pct` | `float \| null` | Income remaining before ordinary EMR reaches 22%. `null` if already at or above 22% at `sweep_floor` |
| `distance_to_24pct` | `float \| null` | Income remaining before ordinary EMR reaches 24%. `null` if already at or above 24% at `sweep_floor` |

---

## Error Responses

### 422 — Validation Error (Pydantic)
Returned automatically by FastAPI for invalid request shape.

### 422 — Service Error
```json
{ "detail": "Unsupported tax year: 2024" }
```

### 500 — Unexpected Error
```json
{ "detail": "An unexpected error occurred. Please try again." }
```

---

## Route Implementation Notes

### Float → Decimal conversion
```python
Decimal(str(request.pension))
```
Never `Decimal(request.pension)` directly.

### Decimal → float conversion
```python
float(point.emr)
```

### SweepMode conversion
```python
SweepMode(request.sweep_mode)  # raises ValueError if invalid
```

### ACA fields passthrough
```python
aptc_monthly=Decimal(str(request.aptc_monthly)),
include_aca=request.include_aca,
```

### sweep_ceiling passthrough
Pass `None` to the service when `sweep_ceiling` is null in the request.

### Planning signals computation
Derived from the returned points array in the route after the service returns.
Scan the points array once. Follow the same pattern as `api/routers/emr.py`.

---

## File Structure

```
api/
  routers/
    total_cost.py      # Route handler
  models/
    total_cost.py      # TotalCostRequest, TotalCostResponse Pydantic models
```

Register router in `api/main.py`.

---

## Tests

`tests/functional/test_total_cost_route.py`:

1. Happy path — `include_aca=false`, valid response shape, all arrays same length
2. Happy path — `include_aca=true`, ACA cliff present in points and planning signals
3. `aca_cliff_sweep_value` in planning signals matches cliff in points array
4. `bracket_boundaries` correctly identifies rate transitions
5. `zero_rate_threshold` correct (sweep value where emr_ordinary > 0)
6. Missing required field (`sweep_mode`) returns 422
7. Invalid `sweep_mode` value returns 422
8. Invalid `filing_status` returns 422
9. Unsupported `tax_year` returns 422 with service error message
10. Negative monetary field returns 422

All 387 existing tests must still pass.

---

## Out of Scope

- Authentication
- Rate limiting
- Caching
- Multi-year projections
- Scenario persistence
- Income planning page logic (separate frontend spec)
