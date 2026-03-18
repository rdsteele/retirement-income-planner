# Spec: MFJ (Married Filing Jointly) Support

**Version:** 1.1
**Status:** Draft
**Covers:** `services/ohio_tax.py`, `data/brackets/ohio_2025.json`,
           `data/brackets/ohio_2026.json`, `data/aca/aca_2026.json`,
           `api/static/emr.html`, `api/static/income.html`,
           `api/static/tax.html`, `api/static/scenarios.html`,
           `api/static/accounts.html`

---

## Purpose

Add MFJ (married filing jointly) support across the full application stack.
Most services already handle `"mfj"` — the primary work is Ohio tax,
frontend dropdowns, and data file updates. This task also remediates all
hardcoded tax years and filing statuses per the rules in CLAUDE.md.

---

## Current State

| Layer | MFJ Status |
|---|---|
| `federal_tax.py` | ✅ Already supported — MFJ brackets in data files |
| `social_security.py` | ✅ Already supported — MFJ thresholds in `ss_thresholds.json` |
| `emr.py` | ✅ Already supported — passes `filing_status` through |
| `total_cost.py` | ✅ Already supported — passes `filing_status` through |
| `aca.py` | ✅ Cliff defined ($128,600), schedule empty — formula fallback until user populates |
| `api/models/emr.py` | ✅ No filing status validation — service raises ValueError if invalid |
| `api/routers/emr.py` | ✅ No changes needed |
| `ohio_tax.py` | ❌ Single filer only — needs `filing_status` parameter and MFJ exemption logic |
| `data/brackets/ohio_2025.json` | ❌ Single exemption amounts only — needs MFJ amounts added |
| `data/brackets/ohio_2026.json` | ❌ Same — needs MFJ amounts added |
| `data/aca/aca_2026.json` | ⚠️ MFJ schedule empty — formula fallback only until user populates |
| All frontend HTML files | ❌ Filing status and tax year hardcoded — must be remediated |

---

## Scope

### In Scope
1. Ohio tax service — add `filing_status` parameter, MFJ personal exemption
2. Ohio data files — add MFJ exemption amounts for 2025 and 2026
3. All frontend pages — replace ALL hardcoded tax years and filing statuses with
   dynamic `APP_CONFIG`-driven dropdowns (required fix per hardcoding rules in
   CLAUDE.md, regardless of MFJ)
4. Backend — audit all services, routers, and models for hardcoded tax year or
   filing status literals and replace with data-driven or config-driven equivalents
5. ACA data — document MFJ schedule as user-populated (no code change needed)

### Out of Scope
- Ohio joint filing credit (MFJ-only, requires earned income — not applicable to
  retirement income scenarios where income is pensions, IRA withdrawals, dividends)
- ACA MFJ schedule population (user provides their own healthcare.gov APTC estimates)
- MFJ-specific scenario validation
- Two-person income entry (the tool models a household as a single income stream)

---

## 1. Ohio Tax Service — `services/ohio_tax.py`

### Change
Add `filing_status: str` parameter to `calculate_ohio_tax()`. Use it to look up
the correct personal exemption amount from the data file.

### MFJ Personal Exemption

Ohio personal exemptions are **per person**. MFJ gets two exemptions (taxpayer +
spouse), so the total exemption is double the per-person amount. The MAGI tiers
use the same thresholds as single.

**Tax Year 2025 — confirmed from official Ohio IT 1040 booklet:**

| Ohio MAGI               | Per Person | MFJ Total (×2) |
|-------------------------|------------|----------------|
| $40,000 or less         | $2,400     | $4,800         |
| $40,001 – $80,000       | $2,150     | $4,300         |
| $80,001 – $749,999      | $1,900     | $3,800         |
| $750,000 or greater     | $0         | $0             |

**Note:** The existing single-filer amounts in `ohio_2025.json` ($2,400/$2,150/$1,900)
are correct and do not need to change. The $750,000+ = $0 tier is the HB96 income
cap — add it to both the single and MFJ tables. The data file needs a new
`personal_exemption_mfj` key with the doubled amounts, and the existing
`personal_exemption` key renamed to `personal_exemption_single`.

**Tax Year 2026** — Ohio transitions to a flat 2.75% rate above $26,050.
Use 2025 per-person exemption amounts as placeholders until the official 2026
Ohio IT 1040 booklet is available. Add a comment in the data file noting this.

### Updated `calculate_ohio_tax()` signature

```python
def calculate_ohio_tax(
    federal_agi: Decimal,
    gross_medical_expenses: Decimal,
    qualifying_retirement_income: Decimal,
    ss_taxable_federal: Decimal,
    tax_year: int,
    filing_status: str = "single",    # NEW — "single" or "mfj"
) -> OhioTaxResult:
```

Default `"single"` preserves backward compatibility with all existing callers
and tests.

### MFJ Exemption Lookup

The data file stores the total MFJ exemption directly (already doubled).
The service selects the correct table based on `filing_status`:

```python
if filing_status == "mfj":
    personal_exemption = _lookup_personal_exemption(ohio_agi, data["personal_exemption_mfj"])
else:
    personal_exemption = _lookup_personal_exemption(ohio_agi, data["personal_exemption_single"])
```

### Retirement Income Credit — MFJ

The retirement income credit table and $200 maximum are the same for MFJ as
single. The eligibility threshold (`ohio_agi - personal_exemption < $100,000`)
uses the combined MFJ exemption (e.g. $4,800 at the lowest tier), which slightly
raises the effective MAGI ceiling for credit eligibility. No change to the
credit lookup logic — just uses the already-computed `personal_exemption`.

### ValueError for unsupported filing status

```python
if filing_status not in ("single", "mfj"):
    raise ValueError(f"Unsupported filing status: {filing_status!r}")
```

---

## 2. Ohio Data Files

### `data/brackets/ohio_2025.json` — updated structure

```json
{
  "tax_year": 2025,
  "brackets": [
    {"from": "0",      "to": "26050",  "base": "0",       "rate": "0.0000",  "excess_over": "0"},
    {"from": "26050",  "to": "100000", "base": "342.00",  "rate": "0.0275",  "excess_over": "26050"},
    {"from": "100000", "to": null,     "base": "2394.32", "rate": "0.03125", "excess_over": "100000"}
  ],
  "personal_exemption_single": [
    {"agi_up_to": "40000",  "amount": "2400"},
    {"agi_up_to": "80000",  "amount": "2150"},
    {"agi_up_to": "749999", "amount": "1900"},
    {"agi_up_to": null,     "amount": "0"}
  ],
  "personal_exemption_mfj": [
    {"agi_up_to": "40000",  "amount": "4800"},
    {"agi_up_to": "80000",  "amount": "4300"},
    {"agi_up_to": "749999", "amount": "3800"},
    {"agi_up_to": null,     "amount": "0"}
  ],
  "retirement_income_credit": [
    {"income_up_to": "500",  "credit": "0"},
    {"income_up_to": "1500", "credit": "25"},
    {"income_up_to": "3000", "credit": "50"},
    {"income_up_to": "5000", "credit": "80"},
    {"income_up_to": "8000", "credit": "130"},
    {"income_up_to": null,   "credit": "200"}
  ],
  "medical_expense_floor_rate": "0.075",
  "magi_credit_threshold": "100000"
}
```

### `data/brackets/ohio_2026.json`

Same structure. Use 2025 exemption amounts as placeholders. Add a `_note`
field or comment indicating 2026 exemptions are unconfirmed pending the
official Ohio IT 1040 booklet.

---

## 3. EMR Service — `services/emr.py`

Pass `filing_status` through to `_compute_ohio_tax_at_point()` and on to
`calculate_ohio_tax()`.

```python
def _compute_ohio_tax_at_point(
    agi: Decimal,
    ss_taxable: Decimal,
    ohio_medical_deduction: Decimal,
    ohio_qualifying_retirement_income: Decimal,
    tax_year: int,
    filing_status: str = "single",    # NEW
) -> Decimal:
    ...
    result = calculate_ohio_tax(
        federal_agi=agi,
        gross_medical_expenses=gross_medical,
        qualifying_retirement_income=ohio_qualifying_retirement_income,
        ss_taxable_federal=ss_taxable,
        tax_year=tax_year,
        filing_status=filing_status,  # NEW
    )
```

The `filing_status` is already available in `calculate_emr()` and present in
the `shared` kwargs dict — it just needs to be forwarded to
`_compute_ohio_tax_at_point()`.

---

## 4. Frontend — Filing Status and Tax Year Dropdown Pattern

### Problem
All five HTML pages currently hardcode filing status and tax year values,
either as `<option>` elements in HTML or as JavaScript constants. This
violates the hardcoding rules in CLAUDE.md.

### Solution
Replace hardcoded values with a page-level `APP_CONFIG` constant at the top
of each page's `<script>` block. Dropdowns are built dynamically from this
config. Adding a new filing status or tax year is a one-line config change.

### Pattern

```javascript
const APP_CONFIG = {
  filingStatuses: [
    { value: 'single', label: 'Single' },
    { value: 'mfj',    label: 'Married Filing Jointly' },
  ],
  taxYears: [2025, 2026],
};
```

### Dropdown population helper

```javascript
function populateSelect(selectId, options, defaultValue) {
  const el = document.getElementById(selectId);
  if (!el) return;
  el.innerHTML = '';
  options.forEach(opt => {
    const o = document.createElement('option');
    o.value = opt.value ?? opt;
    o.textContent = opt.label ?? opt;
    if (String(o.value) === String(defaultValue)) o.selected = true;
    el.appendChild(o);
  });
}

// Called on page load:
populateSelect('filing_status', APP_CONFIG.filingStatuses, 'single');
populateSelect('tax_year', APP_CONFIG.taxYears,
  APP_CONFIG.taxYears[APP_CONFIG.taxYears.length - 1]);
```

### Files to update

| File | Current pattern | Change |
|---|---|---|
| `emr.html` | Hardcoded `<option>` in `<select>` | Replace with dynamic population |
| `tax.html` | Hardcoded `<option>` in `<select>` | Replace with dynamic population |
| `income.html` | JS constant `filing_status: 'single'` | Replace with `APP_CONFIG` + dynamic select |
| `scenarios.html` | Audit for hardcoded filing status or year references | Update if found |
| `accounts.html` | Audit for hardcoded filing status or year references | Update if found |

### Default values
- `filing_status` default: `"single"` (first option — no behavior change for existing users)
- `tax_year` default: most recent year in `APP_CONFIG.taxYears`

---

## 5. ACA MFJ — Data Only

No code change needed. The MFJ ACA schedule is intentionally empty:

```json
"aptc_schedule": {
  "single": [ ... ],
  "mfj": []
}
```

When the `mfj` schedule is empty, `aca.py` falls back to the formula-based
calculation which requires `slcsp_annual_premium` — not currently wired into
the UI. MFJ ACA subsidy amounts will show as zero until the user populates
their schedule.

**To enable MFJ ACA:** User adds APTC estimates from healthcare.gov to
`data/aca/aca_2026.json` under `aptc_schedule.mfj`, same format as the
`single` schedule. No code change required.

---

## 6. Ohio Spec Update — `specs/ohio_tax.md`

Update `ohio_tax.md` to:
- Add `filing_status` to the inputs table
- Update personal exemption section to show per-person amounts, MFJ doubling,
  and the $750,000+ cap tier
- Update data file structure section to show `personal_exemption_single` /
  `personal_exemption_mfj` keys
- Add a MFJ worked example
- Remove "MFJ filing status (single filer only for now)" from Out of Scope

---

## Implementation Order

1. Update `data/brackets/ohio_2025.json` — rename key, add MFJ exemption table,
   add $750,000 cap tier to both
2. Update `data/brackets/ohio_2026.json` — same structure, placeholder amounts
3. Update `services/ohio_tax.py` — add `filing_status` parameter, update
   exemption key lookups
4. Update `services/emr.py` — pass `filing_status` to `_compute_ohio_tax_at_point`
5. **Audit all backend files** — search `services/`, `api/routers/`, `api/models/`
   for hardcoded tax year literals (`2025`, `2026`) and filing status literals
   outside of data files and test fixtures. Replace with data-driven equivalents.
6. **Update all five frontend HTML files** — add `APP_CONFIG`, implement
   `populateSelect` helper, replace all hardcoded filing status and tax year
   values with dynamic population
7. Update `specs/ohio_tax.md`
8. Run full test suite — fix broken tests as you go
9. Add new MFJ unit tests to `tests/unit/test_ohio_tax.py`
10. Add MFJ scenario test to `tests/scenarios/`

---

## Tests

### Existing tests to update
- `tests/unit/test_ohio_tax.py` — update all `calculate_ohio_tax()` calls to
  pass `filing_status="single"` explicitly (or rely on default)
- Any test reading Ohio data file that references the `personal_exemption` key
  directly — update to `personal_exemption_single`

### New unit tests — `tests/unit/test_ohio_tax.py`
1. MFJ $40,000 or less tier: `personal_exemption = 4800`
2. MFJ $40,001–$80,000 tier: `personal_exemption = 4300`
3. MFJ $80,001–$749,999 tier: `personal_exemption = 3800`
4. MFJ $750,000+ tier: `personal_exemption = 0`
5. MFJ retirement income credit eligibility uses combined exemption
6. Unsupported filing status raises `ValueError`
7. MFJ with SS: `ohio_agi = federal_agi - ss_taxable` (same formula as single)

### New scenario test — `tests/scenarios/test_scenario_mfj_ohio_emr.py`
MFJ couple, pension + IRA withdrawals, Ohio included. Verify:
- EMR curve is produced without errors
- Ohio tax components are non-zero
- MFJ exemption ($4,300 or $3,800 depending on AGI) is reflected in results

---

## Worked Example — MFJ Ohio Tax 2025

**Inputs:**
- `federal_agi`: `90000`
- `gross_medical_expenses`: `5000`
- `qualifying_retirement_income`: `70000`
- `ss_taxable_federal`: `0`
- `filing_status`: `"mfj"`

**Calculation flow:**
- Ohio AGI: `90000` (no SS deduction)
- Personal exemption: `3800` (MFJ, AGI $80,001–$749,999 → $1,900 × 2)
- Medical floor: `6750` (90000 × 7.5%) — exceeds gross medical, deduction is zero
- Medical deduction: `0`
- Ohio tax base: `86200` (90000 − 3800 − 0)
- Tax before credits: `342.00 + 2.75% × (86200 − 26050) = 342.00 + 1654.13 = 1996.13` → `1996`
- MAGI less exemption: `86200` — under $100,000, credit applies
- Retirement income credit: `200` (retirement income > $8,000)

**Expected outputs:**
- `ohio_agi`: `90000`
- `personal_exemption`: `3800`
- `medical_deduction`: `0`
- `ohio_tax_base`: `86200`
- `tax_before_credits`: `1996`
- `retirement_income_credit`: `200`
- `ohio_tax`: `1796`
- `effective_rate`: `0.0200`

---

## Notes and Caveats

- **Ohio exemption amounts:** Confirmed from official Ohio IT 1040 booklet.
  Single amounts in existing `ohio_2025.json` are correct — no change needed.
- **Ohio 2026 exemptions:** Use 2025 amounts as placeholders until the official
  2026 Ohio IT 1040 booklet is published.
- **ACA MFJ:** No code change needed. User populates schedule from healthcare.gov.
- **Ohio joint filing credit:** Out of scope — requires earned income not present
  in retirement income scenarios.
