# Spec: Ohio State Income Tax Service

**Version:** 1.1
**Status:** Draft
**Covers:** `services/ohio_tax.py`, `data/brackets/ohio_2025.json`, `data/brackets/ohio_2026.json`

---

## Purpose

Calculate Ohio state income tax liability for single and MFJ filers. Handles Ohio-specific
rules including: progressive bracket calculation, AGI-tiered personal exemption,
medical expense deduction with 7.5% AGI floor, Social Security exemption, and
retirement income credit.

Ohio starts with federal AGI and applies its own adjustments, exemptions, and
bracket schedule.

---

## Inputs

| Field                    | Type      | Description                                                      |
|--------------------------|-----------|------------------------------------------------------------------|
| `federal_agi`            | `Decimal` | Federal adjusted gross income (federal 1040 line 11)            |
| `gross_medical_expenses` | `Decimal` | Total unreimbursed medical/dental expenses before 7.5% floor    |
| `qualifying_retirement_income` | `Decimal` | IRA distributions + pension/annuity income qualifying for retirement income credit |
| `ss_taxable_federal`     | `Decimal` | Taxable SS from federal return (line 6b) — Ohio deducts this    |
| `tax_year`               | `int`     | Supported years: `2025`, `2026`                                  |
| `filing_status`          | `str`     | `"single"` (default) or `"mfj"`                                 |

All `Decimal` inputs must be whole dollar amounts, non-negative.

---

## Outputs

Returns an `OhioTaxResult` dataclass:

| Field                      | Type      | Description                                                    |
|----------------------------|-----------|----------------------------------------------------------------|
| `ohio_agi`                 | `Decimal` | Federal AGI less SS deduction and other Ohio adjustments       |
| `personal_exemption`       | `Decimal` | Exemption amount based on Ohio AGI tier and filing status      |
| `medical_deduction`        | `Decimal` | Allowable medical deduction after 7.5% floor                   |
| `ohio_tax_base`            | `Decimal` | Ohio AGI less exemption less medical deduction                 |
| `tax_before_credits`       | `Decimal` | Ohio bracket tax before applying credits                       |
| `retirement_income_credit` | `Decimal` | Retirement income credit applied (0 if disqualified)           |
| `ohio_tax`                 | `Decimal` | Final Ohio tax after credits                                   |
| `effective_rate`           | `Decimal` | `ohio_tax / ohio_agi`, 4 decimal places                        |

---

## Calculation Rules

### 1. Ohio AGI
```
Ohio AGI = federal_agi - ss_taxable_federal
```
Ohio fully exempts Social Security. The taxable SS amount from the federal return
is deducted on the Ohio Schedule of Adjustments (line 16). If `ss_taxable_federal`
is zero, Ohio AGI equals federal AGI.

### 2. Personal Exemption
Ohio uses a tiered personal exemption based on Ohio AGI. Exemptions are **per person**.
MFJ filers receive two exemptions (taxpayer + spouse), stored as totals in the data file.
The MAGI tier thresholds are the same for single and MFJ.

Amounts reflect HB96 (House Bill 96, effective September 2025), which added a $750,000+
income cap tier returning $0.

**Tax year 2025 — confirmed from official Ohio IT 1040 booklet:**

| Ohio AGI                  | Single    | MFJ (×2 per-person) |
|---------------------------|-----------|---------------------|
| $0 – $40,000              | $2,400    | $4,800              |
| $40,001 – $80,000         | $2,150    | $4,300              |
| $80,001 – $749,999        | $1,900    | $3,800              |
| $750,000 or greater       | $0        | $0                  |

**Tax year 2026** — 2025 amounts used as placeholders pending official Ohio IT 1040
booklet publication.

The service selects the exemption table (`personal_exemption_single` or
`personal_exemption_mfj`) based on `filing_status`. Raises `ValueError` for
unsupported filing statuses.

### 3. Medical Deduction
Ohio allows a deduction for unreimbursed medical and health care expenses exceeding
7.5% of Ohio AGI:
```
medical_floor = round(ohio_agi × 0.075)   # ROUND_HALF_UP to whole dollar
medical_deduction = max(0, gross_medical_expenses - medical_floor)
```
If gross medical expenses are zero or do not exceed the floor, medical deduction is zero.

### 4. Ohio Tax Base
```
ohio_tax_base = max(0, ohio_agi - personal_exemption - medical_deduction)
```

### 5. Bracket Tax Calculation
Ohio uses a cumulative formula (not marginal bracket iteration). For tax year 2025:

| Ohio Taxable Income       | Tax Calculation                                    |
|---------------------------|----------------------------------------------------|
| $0 – $26,050              | $0                                                 |
| $26,051 – $100,000        | $342.00 + 2.75% of excess over $26,050             |
| Over $100,000             | $2,394.32 + 3.125% of excess over $100,000         |

For tax year 2026 (flat rate, HB96):

| Ohio Taxable Income       | Tax Calculation                                    |
|---------------------------|----------------------------------------------------|
| $0 – $26,050              | $0                                                 |
| Over $26,050              | $332.00 + 2.75% of excess over $26,050             |

Apply `ROUND_HALF_UP` to whole dollar after computing the formula result.

### 6. Retirement Income Credit
A nonrefundable credit against Ohio tax for qualifying retirement income.

**Eligibility requirements — all must be met:**
- MAGI less personal exemption is less than $100,000
  (`MAGI = Ohio AGI` when no business income deduction applies)
- Qualifying retirement income received on account of retirement
- Income is included in Ohio AGI
- Taxpayer has not previously claimed the Ohio lump sum retirement credit

For MFJ filers, the combined MFJ personal exemption (e.g. $4,800 at the lowest tier)
is used in the eligibility check, which slightly raises the effective MAGI ceiling.

**Credit tier table (from R.C. § 5747.055):**

| Qualifying Retirement Income | Credit |
|------------------------------|--------|
| $500 or less                 | $0     |
| Over $500 – $1,500           | $25    |
| Over $1,500 – $3,000         | $50    |
| Over $3,000 – $5,000         | $80    |
| Over $5,000 – $8,000         | $130   |
| Over $8,000                  | $200   |

Maximum credit is $200. Credit is nonrefundable — cannot reduce tax below zero.

### 7. Ohio Tax
```
ohio_tax = max(0, tax_before_credits - retirement_income_credit)
```

### 8. Effective Rate
```
effective_rate = ohio_tax / ohio_agi
```
Rounded to 4 decimal places using ROUND_HALF_UP.
If Ohio AGI is zero, effective rate is `Decimal('0')`.

### 9. Data Loading
Bracket thresholds and formula constants are loaded from
`data/brackets/ohio_{year}.json`. The service raises `ValueError`
for unsupported tax years and unsupported filing statuses.

---

## Bracket Data JSON Structure

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

---

## Worked Examples

---

### Example 1 — 2025 Income Profile Proxy (Single)

**Inputs:**
- `federal_agi`: `45370`
- `gross_medical_expenses`: `6557`
- `qualifying_retirement_income`: `47089` (IRA $45,493 + pension $1,596)
- `ss_taxable_federal`: `0`
- `filing_status`: `"single"`

**Calculation flow:**
- Ohio AGI: `45370`
- Personal exemption: `2150` (single, AGI in $40,001–$80,000 tier)
- Medical floor: `3403` (45370 × 7.5%)
- Medical deduction: `3154` (6557 − 3403)
- Ohio tax base: `40066` (45370 − 2150 − 3154)
- Tax before credits: `727` ($342.00 + 2.75% × (40066 − 26050))
- MAGI less exemption: `43220` — under $100,000, credit applies
- Retirement income credit: `200` (retirement income > $8,000)

**Expected outputs:**
- `ohio_agi`: `45370`
- `personal_exemption`: `2150`
- `medical_deduction`: `3154`
- `ohio_tax_base`: `40066`
- `tax_before_credits`: `727`
- `retirement_income_credit`: `200`
- `ohio_tax`: `527`
- `effective_rate`: `0.0116`

---

### Example 2 — Clean Round Numbers, 2.75% Bracket (Single)

**Inputs:**
- `federal_agi`: `60000`
- `gross_medical_expenses`: `8000`
- `qualifying_retirement_income`: `50000`
- `ss_taxable_federal`: `0`
- `filing_status`: `"single"`

**Calculation flow:**
- Ohio AGI: `60000`
- Personal exemption: `2150`
- Medical floor: `4500` (60000 × 7.5%)
- Medical deduction: `3500`
- Ohio tax base: `54350`
- Tax before credits: `1120`
- Retirement income credit: `200`

**Expected outputs:**
- `ohio_agi`: `60000`
- `personal_exemption`: `2150`
- `medical_deduction`: `3500`
- `ohio_tax_base`: `54350`
- `tax_before_credits`: `1120`
- `retirement_income_credit`: `200`
- `ohio_tax`: `920`
- `effective_rate`: `0.0153`

---

### Example 3 — Income Below $26,050 Threshold, Zero Tax (Single)

**Inputs:**
- `federal_agi`: `28000`
- `gross_medical_expenses`: `3000`
- `qualifying_retirement_income`: `20000`
- `ss_taxable_federal`: `0`
- `filing_status`: `"single"`

**Calculation flow:**
- Ohio AGI: `28000`
- Personal exemption: `2400` (AGI ≤ $40,000)
- Medical floor: `2100`
- Medical deduction: `900`
- Ohio tax base: `24700` — below $26,050, zero bracket tax
- Retirement income credit: `200` (not applied — tax already zero)

**Expected outputs:**
- `ohio_agi`: `28000`
- `personal_exemption`: `2400`
- `medical_deduction`: `900`
- `ohio_tax_base`: `24700`
- `tax_before_credits`: `0`
- `retirement_income_credit`: `200`
- `ohio_tax`: `0`
- `effective_rate`: `0.0000`

---

### Example 4 — High Medical Expenses, Minimal Tax (Single)

**Inputs:**
- `federal_agi`: `40000`
- `gross_medical_expenses`: `10000`
- `qualifying_retirement_income`: `30000`
- `ss_taxable_federal`: `0`
- `filing_status`: `"single"`

**Calculation flow:**
- Ohio AGI: `40000`
- Personal exemption: `2400`
- Medical floor: `3000`
- Medical deduction: `7000`
- Ohio tax base: `30600`
- Tax before credits: `467`
- Retirement income credit: `200`

**Expected outputs:**
- `ohio_agi`: `40000`
- `personal_exemption`: `2400`
- `medical_deduction`: `7000`
- `ohio_tax_base`: `30600`
- `tax_before_credits`: `467`
- `retirement_income_credit`: `200`
- `ohio_tax`: `267`
- `effective_rate`: `0.0067`

---

### Example 5 — Income Into 3.125% Bracket, Credit Disqualified (Single)

**Inputs:**
- `federal_agi`: `110000`
- `gross_medical_expenses`: `5000`
- `qualifying_retirement_income`: `90000`
- `ss_taxable_federal`: `0`
- `filing_status`: `"single"`

**Calculation flow:**
- Ohio AGI: `110000`
- Personal exemption: `1900` (AGI > $80,000)
- Medical floor: `8250` — exceeds gross medical, deduction is zero
- Ohio tax base: `108100`
- Tax before credits: `2647`
- MAGI less exemption: `108100` — exceeds $100,000, credit disqualified

**Expected outputs:**
- `ohio_agi`: `110000`
- `personal_exemption`: `1900`
- `medical_deduction`: `0`
- `ohio_tax_base`: `108100`
- `tax_before_credits`: `2647`
- `retirement_income_credit`: `0`
- `ohio_tax`: `2647`
- `effective_rate`: `0.0241`

---

### Example 6 — MFJ Pension + IRA Withdrawals, 2025

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
- Tax before credits: `1996` ($342.00 + 2.75% × (86200 − 26050) = 342.00 + 1654.13 → rounded)
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

## Edge Cases

| Scenario                                           | Expected Behavior                                              |
|----------------------------------------------------|----------------------------------------------------------------|
| `federal_agi = 0`                                  | All outputs zero                                               |
| `gross_medical_expenses = 0`                       | Medical deduction is zero                                      |
| Medical expenses do not exceed 7.5% floor         | Medical deduction is zero                                      |
| `ss_taxable_federal > 0`                           | Ohio AGI reduced by SS amount before all other calculations    |
| MAGI less exemption ≥ $100,000                     | Retirement income credit is zero                               |
| `qualifying_retirement_income ≤ 500`               | Retirement income credit is zero                               |
| Credit exceeds tax before credits                  | `ohio_tax = 0` (credit is nonrefundable)                       |
| `ohio_tax_base` falls in zero bracket (≤ $26,050)  | `tax_before_credits = 0`                                       |
| Unsupported `tax_year`                             | Raise `ValueError`                                             |
| Unsupported `filing_status`                        | Raise `ValueError`                                             |
| `filing_status = "mfj"`                            | Use `personal_exemption_mfj` table (doubled per-person amount) |

---

## Out of Scope for This Service

- Ohio joint filing credit (MFJ-only; requires earned income — not applicable to
  retirement income scenarios)
- Ohio school district income tax (separate tax, separate service if needed)
- Lump sum retirement credit
- Senior citizen credit (taxpayer is under 65)
- Business income deduction (no business income in scope)
- Municipal/local income tax
- Ohio minimum income credit
