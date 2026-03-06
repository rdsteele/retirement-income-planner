# Spec: FastAPI EMR Route

**Version:** 1.0
**Status:** Draft
**Covers:** `api/routers/emr.py`, `api/models/emr.py`

---

## Purpose

Expose the `calculate_emr` service as an HTTP endpoint. The route is a thin
wrapper — it deserializes the request, calls the service, converts the result
to a frontend-friendly JSON shape, and handles errors. No business logic lives
here.

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
POST /api/emr
Content-Type: application/json
```

---

## Request Model

Pydantic model `EMRRequest` in `api/models/emr.py`.

All monetary fields are `float`, non-negative. The route converts them to
`Decimal` before passing to the service.

### Fixed Income Fields (all optional, default `0.0`)

| Field                               | Type    | Description                              |
|-------------------------------------|---------|------------------------------------------|
| `pension`                           | `float` | Fixed pension or annuity income          |
| `interest`                          | `float` | Taxable interest income                  |
| `ordinary_dividends`                | `float` | Non-qualified dividends                  |
| `inherited_ira_rmd`                 | `float` | Inherited IRA required distributions     |
| `ss_benefit`                        | `float` | Gross Social Security benefit            |
| `qualified_dividends`               | `float` | Qualified dividends (preferential rate)  |
| `fixed_ltcg`                        | `float` | Fixed LTCG already realized              |
| `tax_exempt_interest`               | `float` | Tax-exempt interest income               |

### Mode and Sweep Fields

| Field                | Type    | Default         | Description                              |
|----------------------|---------|-----------------|------------------------------------------|
| `sweep_mode`         | `str`   | required        | `"ordinary"` or `"preferential"`         |
| `variable_ordinary`  | `float` | `0.0`           | Fixed IRA/Roth amount in PREFERENTIAL mode |
| `sweep_floor`        | `float` | `0.0`           | Start of sweep range                     |
| `sweep_ceiling`      | `float` | `null`          | End of sweep range (null = default 24% bracket top) |
| `sweep_step`         | `float` | `100.0`         | Increment between sweep points           |
| `filing_status`      | `str`   | required        | `"single"` or `"mfj"`                   |
| `tax_year`           | `int`   | required        | e.g. `2025`                              |

### Ohio Fields (all optional)

| Field                                  | Type    | Default  | Description                                    |
|----------------------------------------|---------|----------|------------------------------------------------|
| `include_ohio`                         | `bool`  | `false`  | Include Ohio tax in EMR calculation            |
| `ohio_medical_deduction`               | `float` | `0.0`    | Pre-computed Ohio medical deduction            |
| `ohio_qualifying_retirement_income`    | `float` | `0.0`    | IRA + pension qualifying for retirement credit |

### Request Validation (Pydantic)

- All monetary fields: `ge=0` (non-negative)
- `sweep_mode`: must be `"ordinary"` or `"preferential"`
- `filing_status`: must be `"single"` or `"mfj"`
- `tax_year`: must be a positive integer
- `sweep_step`: `gt=0` (must be positive)
- `sweep_floor`: `ge=0`
- `sweep_ceiling`: `gt=0` if provided

Pydantic validation errors are automatically returned as 422 by FastAPI.
Service-layer `ValueError` (e.g. unsupported tax year) is caught by the route
and returned as a 422 with a structured error body.

---

## Response Model

Returns HTTP 200 with `EMRResponse` JSON body.

All numeric values are `float`. No `Decimal`, no Python-specific types.

```json
{
  "sweep_mode": "ordinary",
  "filing_status": "single",
  "tax_year": 2025,
  "points": {
    "income":         [0.0, 100.0, 200.0],
    "total_tax":      [700.0, 712.0, 724.0],
    "emr":            [0.10, 0.10, 0.12],
    "components": {
      "ordinary":       [0.10, 0.10, 0.12],
      "ss_torpedo":     [0.0,  0.0,  0.0],
      "pref_stacking":  [0.0,  0.0,  0.0],
      "niit":           [0.0,  0.0,  0.0],
      "ohio":           [0.0,  0.0,  0.0]
    },
    "ss_taxable":         [0.0, 0.0, 0.0],
    "ss_inclusion_rate":  [0.0, 0.0, 0.0],
    "taxable_ordinary":   [7000.0, 7100.0, 7200.0],
    "ohio_tax":           [0.0, 0.0, 0.0]
  },
  "irmaa_thresholds": [106000.0, 133000.0, 167000.0, 200000.0, 500000.0],
  "planning_signals": {
    "ltcg_0pct_remaining":  26350.0,
    "torpedo_active":       false,
    "ss_fully_taxable":     false,
    "distance_to_22pct":    19350.0,
    "distance_to_24pct":    null
  }
}
```

### Points Array

Parallel arrays — all arrays have the same length, one entry per sweep point.
This shape is directly consumable by Plotly without any frontend transformation.

### Planning Signals

Derived from the points array by the route after the service returns. All
distances are relative to the current `sweep_floor`.

| Signal                  | Type            | Description                                                  |
|-------------------------|-----------------|--------------------------------------------------------------|
| `ltcg_0pct_remaining`   | `float \| null` | Income remaining before LTCG enters 15% bracket. `null` if already past threshold or `sweep_mode = "ordinary"` with no preferential income |
| `torpedo_active`        | `bool`          | True if any point in the sweep has `emr_ss_torpedo > 0`      |
| `ss_fully_taxable`      | `bool`          | True if SS inclusion rate has reached 85% at `sweep_floor`   |
| `distance_to_22pct`     | `float \| null` | Income remaining before ordinary EMR reaches 22%. `null` if already at or above 22% at `sweep_floor` |
| `distance_to_24pct`     | `float \| null` | Income remaining before ordinary EMR reaches 24%. `null` if already at or above 24% at `sweep_floor` |

---

## Error Responses

### 422 — Validation Error (Pydantic)
Returned automatically by FastAPI for invalid request shape.

### 422 — Service Error
Returned when the service raises `ValueError` (e.g. unsupported tax year):

```json
{
  "detail": "Unsupported tax year: 2024"
}
```

### 500 — Unexpected Error
Returned for any unhandled exception. Log the full traceback server-side.
Return a generic message to the client:

```json
{
  "detail": "An unexpected error occurred. Please try again."
}
```

---

## Route Implementation Notes

### Float → Decimal conversion
Convert all incoming `float` fields to `Decimal` using `str()` as intermediary
to avoid float precision issues:
```python
Decimal(str(request.pension))
```
Never `Decimal(request.pension)` directly — that captures float imprecision.

### Decimal → float conversion
Convert all `Decimal` values in the service response to `float` for JSON
serialization:
```python
float(point.emr)
```

### SweepMode conversion
Convert `sweep_mode` string to `SweepMode` enum before calling service:
```python
SweepMode(request.sweep_mode)  # raises ValueError if invalid — caught by route
```

### sweep_ceiling passthrough
If `sweep_ceiling` is `null` in the request, pass `None` to the service —
the service will compute the default from bracket data.

### Planning signals computation
Planning signals are derived from the returned points array in the route,
not in the service. Keep signal derivation logic simple — scan the points
array once after the service returns.

---

## File Structure

```
api/
  __init__.py
  main.py              # FastAPI app, mounts router
  routers/
    __init__.py
    emr.py             # Route handler
  models/
    __init__.py
    emr.py             # EMRRequest, EMRResponse Pydantic models
```

---

## Out of Scope for This Route

- Authentication
- Rate limiting
- Caching
- Multi-year projections
- Scenario persistence (save/load)
- Income planner endpoint (separate route, separate spec)
