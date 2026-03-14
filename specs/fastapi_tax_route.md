# Spec: FastAPI Tax Detail Route

**Version:** 1.0
**Status:** Draft
**Covers:** `api/routers/tax.py`, `api/models/tax.py`

---

## Purpose

Expose a point-in-time tax calculation as an HTTP endpoint. Given a set of
income inputs, returns a complete federal and Ohio tax breakdown — AGI, taxable
income, bracket-by-bracket detail, total tax, and effective rate. No sweep
machinery. Consumed by the tax detail page for interactive point-in-time
analysis.

---

## Architecture Rules

- Routes import from `services/` — never the reverse
- All validation that protects service correctness lives in the service layer
- The route catches `ValueError` from services and returns structured 422 responses
- `Decimal` is used inside services. The route converts all `Decimal` values to
  `float` at the API boundary before returning JSON
- Pydantic models are used for request deserialization and response serialization
- No tax logic lives in the route

---

## Endpoint

```
POST /api/tax
Content-Type: application/json
```

---

## Request Model

Pydantic model `TaxRequest` in `api/models/tax.py`.

All monetary fields are `float`, non-negative. The route converts them to
`Decimal` before passing to services.

### Income Fields (all optional, default `0.0`)

| Field | Type | Description |
|---|---|---|
| `pension` | `float` | Taxable pension and annuity income |
| `interest` | `float` | Taxable interest income |
| `ordinary_dividends` | `float` | Non-qualified dividends |
| `qualified_dividends` | `float` | Qualified dividends (preferential rate) |
| `ira_distributions` | `float` | Taxable IRA/401k distributions, RMDs, Roth conversions |
| `ss_benefit` | `float` | Gross Social Security benefit (taxability computed) |
| `fixed_ltcg` | `float` | Long-term capital gains |
| `tax_exempt_interest` | `float` | Tax-exempt interest (counts toward SS provisional income and ACA MAGI) |
| `wages` | `float` | W-2 wages (not typical for retirees but supported) |

### Adjustment Fields (all optional, default `0.0`)

| Field | Type | Description |
|---|---|---|
| `above_the_line_adjustments` | `float` | HSA contributions, IRA deductions, etc. |
| `additional_deductions` | `float` | QBI deduction, excess itemized deductions over standard |

### Settings Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `filing_status` | `str` | required | `"single"` or `"mfj"` |
| `tax_year` | `int` | required | e.g. `2026` |

### Ohio Fields (all optional)

| Field | Type | Default | Description |
|---|---|---|---|
| `include_ohio` | `bool` | `false` | Include Ohio tax calculation |
| `gross_medical_expenses` | `float` | `0.0` | Total unreimbursed medical expenses before 7.5% floor |
| `ohio_qualifying_retirement_income` | `float` | `0.0` | IRA + pension qualifying for Ohio retirement credit |

### Request Validation (Pydantic)

- All monetary fields: `ge=0`
- `filing_status`: must be `"single"` or `"mfj"`
- `tax_year`: positive integer

---

## Route Calculation Logic

The route orchestrates three service calls and assembles the response.
No tax math lives in the route.

### Step 1 — SS Taxability
Call `services.social_security.calculate_social_security_taxability()`:
```python
provisional_income = (
    pension + interest + ordinary_dividends + ira_distributions
    + wages + fixed_ltcg + qualified_dividends
    - above_the_line_adjustments
    + tax_exempt_interest
    + ss_benefit * Decimal('0.5')
)
ss_result = calculate_social_security_taxability(
    ss_benefit=ss_benefit,
    provisional_income=provisional_income,
    filing_status=filing_status,
)
ss_taxable = ss_result.taxable_amount
```

### Step 2 — Federal Tax
Compute taxable income and call `services.federal_tax.calculate_federal_tax()`:
```python
total_ordinary = (
    pension + interest + ordinary_dividends + ira_distributions
    + wages + ss_taxable
    - above_the_line_adjustments
)
standard_deduction = # loaded from bracket data for filing_status / tax_year
taxable_ordinary = max(0, total_ordinary - standard_deduction - additional_deductions)
total_preferential = qualified_dividends + fixed_ltcg

federal_result = calculate_federal_tax(
    ordinary_income=taxable_ordinary,
    preferential_income=total_preferential,
    filing_status=filing_status,
    tax_year=tax_year,
)
```

### Step 3 — Ohio Tax (optional)
Only when `include_ohio = True`:
```python
federal_agi = total_ordinary + total_preferential
ohio_result = calculate_ohio_tax(
    federal_agi=federal_agi,
    gross_medical_expenses=gross_medical_expenses,
    qualifying_retirement_income=ohio_qualifying_retirement_income,
    ss_taxable_federal=ss_taxable,
    tax_year=tax_year,
)
```

---

## Response Model

Returns HTTP 200 with `TaxResponse` JSON body.

All numeric values are `float`. No `Decimal`, no Python-specific types.

```json
{
  "filing_status": "single",
  "tax_year": 2026,
  "inputs_summary": {
    "gross_ordinary_income": 21270.0,
    "ss_taxable": 0.0,
    "above_the_line_adjustments": 5400.0,
    "agi": 15870.0,
    "standard_deduction": 16100.0,
    "additional_deductions": 23.0,
    "taxable_ordinary": 0.0,
    "taxable_preferential": 46500.0
  },
  "federal": {
    "ordinary_income_tax": 0.0,
    "preferential_income_tax": 0.0,
    "total_tax": 0.0,
    "effective_rate": 0.0,
    "marginal_bracket_rate": 0.10,
    "bracket_breakdown": [
      {
        "rate": 0.10,
        "from": 0.0,
        "to": 12400.0,
        "income_taxed": 0.0,
        "tax_amount": 0.0
      }
    ],
    "preferential_breakdown": [
      {
        "rate": 0.00,
        "from": 0.0,
        "to": 49450.0,
        "income_taxed": 46500.0,
        "tax_amount": 0.0
      }
    ]
  },
  "ohio": {
    "included": true,
    "ohio_agi": 15870.0,
    "personal_exemption": 2400.0,
    "medical_deduction": 0.0,
    "ohio_tax_base": 13470.0,
    "tax_before_credits": 0.0,
    "retirement_income_credit": 200.0,
    "ohio_tax": 0.0,
    "effective_rate": 0.0
  },
  "summary": {
    "total_federal_tax": 0.0,
    "total_ohio_tax": 0.0,
    "total_tax": 0.0,
    "overall_effective_rate": 0.0
  }
}
```

### inputs_summary fields

Derived values shown between inputs and bracket tables — the "bridge" that
makes the calculation transparent:

| Field | Description |
|---|---|
| `gross_ordinary_income` | pension + interest + ordinary_dividends + ira_distributions + wages (before SS, before adjustments) |
| `ss_taxable` | Taxable portion of SS benefit |
| `above_the_line_adjustments` | Pass-through from request |
| `agi` | Federal AGI = gross_ordinary + ss_taxable + preferential - above_the_line_adjustments |
| `standard_deduction` | Standard deduction for filing_status / tax_year from bracket data |
| `additional_deductions` | Pass-through from request |
| `taxable_ordinary` | max(0, agi - standard_deduction - additional_deductions - preferential) |
| `taxable_preferential` | qualified_dividends + fixed_ltcg |

### bracket_breakdown and preferential_breakdown

Each entry represents one bracket. `from` and `to` are the bracket boundaries
(not the income applied). `income_taxed` is the amount of income that fell in
this bracket. `to` is `null` for the top bracket — serialize as a very large
number (e.g. `999999999.0`) for JSON compatibility.

Only include brackets where `income_taxed > 0` OR the bracket is the first one
(so the table always shows at least one row).

### ohio fields

When `include_ohio = false`, return `"ohio": {"included": false}` with all
other fields omitted.

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

### Standard deduction loading
Use `services.data_loader.load_federal_data(tax_year)` to retrieve the
standard deduction for the response `inputs_summary`. This is the same
data loader used by the EMR service.

### SS provisional income
Provisional income includes 50% of gross SS benefit, not taxable SS.
SS taxability is determined by the social security service.

---

## File Structure

```
api/
  routers/
    tax.py         # Route handler
  models/
    tax.py         # TaxRequest, TaxResponse Pydantic models
```

Register router in `api/main.py`.

---

## Tests

`tests/functional/test_tax_route.py`:

1. Happy path — single filer, 2026, federal only, correct response shape
2. Happy path — include_ohio=true, Ohio fields populated
3. SS taxability computed correctly (ss_benefit > 0)
4. inputs_summary fields correct (AGI, taxable_ordinary, taxable_preferential)
5. bracket_breakdown shows correct income_taxed and tax_amount per bracket
6. preferential_breakdown correct when LTCG straddles 0%/15% boundary
7. Missing filing_status returns 422
8. Unsupported tax_year returns 422 with service error message
9. include_ohio=false returns ohio.included=false with no other ohio fields
10. All income fields zero returns zero tax

All existing tests must still pass. ruff and mypy clean.

---

## Out of Scope

- Sweep calculation (use `/api/emr` for sweeps)
- ACA subsidy interaction
- IRMAA calculation
- AMT
- Tax credits (foreign tax credit, child tax credit, etc.)
- Multi-year projection
- Scenario persistence
