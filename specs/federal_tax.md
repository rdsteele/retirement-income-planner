# Spec: Federal Income Tax Service

**Version:** 1.0  
**Status:** Draft  
**Covers:** `services/federal_tax.py`, `data/brackets/federal_2025.json`, `data/brackets/federal_2026.json`

---

## Purpose

Calculate federal income tax liability applying IRS preferential income stacking rules.
Ordinary income fills brackets from the bottom; LTCG and qualified dividends stack on top
and are taxed using the preferential rate schedule.

This service receives pre-computed taxable income. Deductions and adjustments are the
responsibility of the caller.

---

## Inputs

| Field               | Type       | Description                                              |
|---------------------|------------|----------------------------------------------------------|
| `ordinary_income`   | `Decimal`  | Taxable ordinary income net of all deductions            |
| `preferential_income` | `Decimal` | LTCG + qualified dividends combined                     |
| `filing_status`     | `str`      | `"single"` or `"mfj"`                                   |
| `tax_year`          | `int`      | `2025` or `2026`                                         |

All `Decimal` inputs must be whole dollar amounts, non-negative.

---

## Outputs

Returns a `FederalTaxResult` dataclass:

| Field                    | Type                    | Description                                          |
|--------------------------|-------------------------|------------------------------------------------------|
| `ordinary_income_tax`    | `Decimal`               | Tax on ordinary income only                          |
| `preferential_income_tax`| `Decimal`               | Tax on LTCG/qualified dividends only                 |
| `total_tax`              | `Decimal`               | Sum of ordinary + preferential tax                   |
| `effective_rate`         | `Decimal`               | `total_tax / (ordinary + preferential)`, 4 decimals  |
| `marginal_bracket_rate`  | `Decimal`               | Statutory rate of the bracket the top dollar of ordinary income falls into |
| `bracket_breakdown`      | `list[BracketDetail]`   | Per-bracket detail for ordinary income               |

`BracketDetail` dataclass:

| Field          | Type      | Description                            |
|----------------|-----------|----------------------------------------|
| `rate`         | `Decimal` | Bracket rate e.g. `Decimal('0.22')`    |
| `income_taxed` | `Decimal` | Amount of income taxed in this bracket |
| `tax_amount`   | `Decimal` | Tax owed for this bracket              |

---

## Calculation Rules

### 1. Stacking Order
Ordinary income fills brackets from the bottom. Preferential income (LTCG + qualified
dividends) stacks on top of ordinary income and is taxed using the preferential schedule.

### 2. Ordinary Income Tax
Apply ordinary income brackets sequentially from the lowest rate upward. For each bracket:
- Income taxed = `min(residual_income, bracket_range)`
- Tax amount = `round(income_taxed * rate)` using `ROUND_HALF_UP`
- Residual carries forward to the next bracket

### 3. Preferential Income Tax
LTCG/qualified dividends stack on top of ordinary income within the preferential brackets.
For each preferential bracket:
- Determine how much of the bracket lies above ordinary income
- Tax the portion of preferential income that falls in this bracket
- Apply `round(income_taxed * rate)` using `ROUND_HALF_UP`

### 4. Effective Rate
```
effective_rate = total_tax / (ordinary_income + preferential_income)
```
Rounded to 4 decimal places. If total income is zero, effective rate is `Decimal('0')`.

### 5. Marginal Bracket Rate
The statutory rate of the ordinary income bracket that the top dollar of ordinary income
falls into. If ordinary income is zero, marginal bracket rate is `Decimal('0.10')` (the
lowest bracket rate).

### 6. Data Loading
Bracket data is loaded from:
- `data/brackets/federal_2025.json`
- `data/brackets/federal_2026.json`

The service must raise a `ValueError` for unsupported tax years.
The service must raise a `ValueError` for unsupported filing statuses.

---

## Bracket Data JSON Structure

Each bracket file contains both filing statuses and both bracket types.

```json
{
  "tax_year": 2025,
  "ordinary": {
    "single": [
      {"rate": "0.10", "from": "0",      "to": "11925"},
      {"rate": "0.12", "from": "11925",  "to": "48475"},
      {"rate": "0.22", "from": "48475",  "to": "103350"},
      {"rate": "0.24", "from": "103350", "to": "197300"},
      {"rate": "0.32", "from": "197300", "to": "250525"},
      {"rate": "0.35", "from": "250525", "to": "626350"},
      {"rate": "0.37", "from": "626350", "to": null}
    ],
    "mfj": [
      {"rate": "0.10", "from": "0",      "to": "23850"},
      {"rate": "0.12", "from": "23850",  "to": "96950"},
      {"rate": "0.22", "from": "96950",  "to": "206700"},
      {"rate": "0.24", "from": "206700", "to": "394600"},
      {"rate": "0.32", "from": "394600", "to": "501050"},
      {"rate": "0.35", "from": "501050", "to": "751600"},
      {"rate": "0.37", "from": "751600", "to": null}
    ]
  },
  "preferential": {
    "single": [
      {"rate": "0.00", "from": "0",      "to": "48350"},
      {"rate": "0.15", "from": "48350",  "to": "533400"},
      {"rate": "0.20", "from": "533400", "to": null}
    ],
    "mfj": [
      {"rate": "0.00", "from": "0",      "to": "96700"},
      {"rate": "0.15", "from": "96700",  "to": "600050"},
      {"rate": "0.20", "from": "600050", "to": null}
    ]
  }
}
```

- All monetary values are strings to preserve precision when loading into `Decimal`
- `"to": null` indicates the top bracket with no upper limit
- `"from"` is the bracket floor (inclusive), `"to"` is the bracket ceiling (inclusive)

---

## Worked Examples

All examples use tax year 2025. These examples are the basis for unit tests.

---

### Example 1 — Single, ordinary income only in multiple brackets

**Inputs:**
- `ordinary_income`: `60000`
- `preferential_income`: `10000`
- `filing_status`: `"single"`
- `tax_year`: `2025`

**Ordinary income bracket breakdown:**

| Bracket | Income Taxed | Tax Amount |
|---------|-------------|------------|
| 10%     | $11,925     | $1,192     |
| 12%     | $36,550     | $4,386     |
| 22%     | $11,525     | $2,536     |

**Preferential income (stacks above $60,000 — fully in 15% LTCG bracket):**

| Bracket | Income Taxed | Tax Amount |
|---------|-------------|------------|
| 15%     | $10,000     | $1,500     |

**Expected outputs:**
- `ordinary_income_tax`: `8114`
- `preferential_income_tax`: `1500`
- `total_tax`: `9614`
- `effective_rate`: `0.1373`
- `marginal_bracket_rate`: `0.22`

---

### Example 2 — MFJ, ordinary income spans multiple brackets

**Inputs:**
- `ordinary_income`: `100000`
- `preferential_income`: `20000`
- `filing_status`: `"mfj"`
- `tax_year`: `2025`

**Ordinary income bracket breakdown:**

| Bracket | Income Taxed | Tax Amount |
|---------|-------------|------------|
| 10%     | $23,850     | $2,385     |
| 12%     | $73,100     | $8,772     |
| 22%     | $3,050      | $671       |

**Preferential income (stacks above $100,000 — fully in 15% LTCG bracket):**

| Bracket | Income Taxed | Tax Amount |
|---------|-------------|------------|
| 15%     | $20,000     | $3,000     |

**Expected outputs:**
- `ordinary_income_tax`: `11828`
- `preferential_income_tax`: `3000`
- `total_tax`: `14828`
- `effective_rate`: `0.1236`
- `marginal_bracket_rate`: `0.22`

---

### Example 3 — Single, preferential income straddles 0%/15% LTCG boundary

**Inputs:**
- `ordinary_income`: `40000`
- `preferential_income`: `20000`
- `filing_status`: `"single"`
- `tax_year`: `2025`

Ordinary income ends at $40,000. The 0% LTCG bracket extends to $48,350.
So $8,350 of preferential income is taxed at 0%, remaining $11,650 at 15%.

**Ordinary income bracket breakdown:**

| Bracket | Income Taxed | Tax Amount |
|---------|-------------|------------|
| 10%     | $11,925     | $1,192     |
| 12%     | $28,075     | $3,369     |

**Preferential income breakdown:**

| Bracket | Income Taxed | Tax Amount |
|---------|-------------|------------|
| 0%      | $8,350      | $0         |
| 15%     | $11,650     | $1,748     |

**Expected outputs:**
- `ordinary_income_tax`: `4561`
- `preferential_income_tax`: `1748`
- `total_tax`: `6309`
- `effective_rate`: `0.1052`
- `marginal_bracket_rate`: `0.12`

---

## Edge Cases

| Scenario                              | Expected Behavior                                              |
|---------------------------------------|----------------------------------------------------------------|
| `ordinary_income = 0`                 | No ordinary tax. Preferential income stacks from bottom of LTCG brackets. `marginal_bracket_rate = Decimal('0.10')` |
| `preferential_income = 0`             | No preferential tax. Only ordinary brackets apply.            |
| Both inputs zero                      | All outputs zero. `effective_rate = Decimal('0')`.            |
| Unsupported `tax_year`                | Raise `ValueError`                                            |
| Unsupported `filing_status`           | Raise `ValueError`                                            |
| Income in top bracket (no `to` limit) | Top bracket absorbs all remaining income                      |

---

## Out of Scope for This Service

- Standard or itemized deduction calculation
- Social Security taxability
- NIIT (3.8% surtax)
- State income tax
- AMT
- Tax credits