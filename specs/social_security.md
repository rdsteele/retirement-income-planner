# Spec: Social Security Taxability Service

**Version:** 1.0
**Status:** Draft
**Covers:** `services/social_security.py`

---

## Purpose

Calculate the taxable portion of Social Security benefits using the IRS provisional
income formula. This service determines how much of a taxpayer's SS benefit is
included in federal AGI.

This is a standalone service — it has no dependency on the federal tax or Ohio tax
services. It is also consumed by the marginal rate service, which calls it repeatedly
to model how taxable SS changes as income varies.

---

## Background — Why This Matters for Planning

The provisional income formula creates the **tax torpedo** effect: a range of income
where each additional dollar of ordinary income causes more than one dollar to become
taxable (the new income dollar plus a portion of SS becoming taxable). This produces
a pronounced spike in the marginal effective tax rate that is one of the primary
planning insights this tool is designed to reveal.

In the 50% inclusion tier: each $1 of new ordinary income effectively adds $1.50 to
taxable income.
In the 85% inclusion tier: each $1 of new ordinary income effectively adds $1.85 to
taxable income.

---

## Inputs

| Field                  | Type      | Description                                              |
|------------------------|-----------|----------------------------------------------------------|
| `ss_benefit`           | `Decimal` | Total annual Social Security benefit (gross, not taxable)|
| `agi_excluding_ss`     | `Decimal` | AGI from all non-SS sources (wages, IRA, dividends, etc.)|
| `tax_exempt_interest`  | `Decimal` | Tax-exempt interest income (e.g. municipal bond interest)|
| `filing_status`        | `str`     | `"single"` or `"mfj"`                                   |

All `Decimal` inputs must be whole dollar amounts, non-negative.

---

## Outputs

Returns a `SocialSecurityResult` dataclass:

| Field                  | Type      | Description                                              |
|------------------------|-----------|----------------------------------------------------------|
| `provisional_income`   | `Decimal` | Computed provisional income                              |
| `taxable_ss`           | `Decimal` | Taxable portion of SS benefit                            |
| `inclusion_rate`       | `Decimal` | `taxable_ss / ss_benefit`, 4 decimal places              |
| `tier`                 | `str`     | `"none"`, `"fifty_percent"`, or `"eighty_five_percent"`  |

If `ss_benefit` is zero, `provisional_income` is still computed normally
(`agi_excluding_ss + tax_exempt_interest`), `taxable_ss` and `inclusion_rate`
are `Decimal('0')`, and `tier` is `"none"`.

---

## Calculation Rules

### 1. Provisional Income
```
provisional_income = agi_excluding_ss + tax_exempt_interest + (ss_benefit × 0.50)
```
Round `ss_benefit × 0.50` to two decimal places using `ROUND_HALF_UP` before adding.

### 2. Data Loading

Thresholds and inclusion rates are loaded from `data/ss_thresholds.json` — a
single config file outside the annual bracket files. These values are defined
in federal law and have not changed since 1993. They are stored in config for
consistency with other services and to avoid magic numbers in service code.

**Config file structure** (`data/ss_thresholds.json`):
```json
{
  "single": {
    "tier_1_threshold": "25000",
    "tier_2_threshold": "34000"
  },
  "mfj": {
    "tier_1_threshold": "32000",
    "tier_2_threshold": "44000"
  },
  "tier_1_inclusion_rate": "0.50",
  "tier_2_inclusion_rate": "0.85",
  "maximum_inclusion_rate": "0.85"
}
```

All values loaded as `Decimal`.

Filing status thresholds for reference:

| Filing Status | Tier 1 Threshold | Tier 2 Threshold |
|---------------|------------------|------------------|
| Single        | $25,000          | $34,000          |
| MFJ           | $32,000          | $44,000          |

### 3. Taxable SS Calculation

**Below Tier 1 threshold:**
```
taxable_ss = 0
tier = "none"
```

**Between Tier 1 and Tier 2 (50% tier):**
```
taxable_ss = min(
    0.50 × (provisional_income - tier_1_threshold),
    0.50 × ss_benefit
)
tier = "fifty_percent"
```

**Above Tier 2 threshold (85% tier):**
```
tier_1_range   = tier_2_threshold - tier_1_threshold   # $9,000 single / $12,000 MFJ
max_tier_1     = min(0.50 × ss_benefit, 0.50 × tier_1_range)
tier_2_amount  = 0.85 × (provisional_income - tier_2_threshold)
taxable_ss     = min(0.85 × ss_benefit, tier_2_amount + max_tier_1)
tier = "eighty_five_percent"
```

All intermediate amounts rounded to two decimal places using `ROUND_HALF_UP`.
Final `taxable_ss` rounded to whole dollar using `ROUND_HALF_UP`.

### 4. Inclusion Rate
```
inclusion_rate = taxable_ss / ss_benefit
```
Rounded to 4 decimal places. If `ss_benefit` is zero, `inclusion_rate` is `Decimal('0')`.

### 5. Maximum Taxable SS
The maximum taxable SS benefit is always **85% of the gross benefit**. No more than
85% is ever taxable regardless of income level.

---

## Worked Examples

All examples: Single filer. `tax_exempt_interest = 0` unless stated.

---

### Example 1 — Below Threshold, No Taxable SS

**Inputs:**
- `ss_benefit`: `20000`
- `agi_excluding_ss`: `15000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`

**Calculation:**
- Provisional income: `15000 + 0 + 10000 = 25000`
- PI = $25,000 — exactly at threshold, below is 0%

**Expected outputs:**
- `provisional_income`: `25000`
- `taxable_ss`: `0`
- `inclusion_rate`: `0.0000`
- `tier`: `"none"`

---

### Example 2 — In 50% Tier, Partial Inclusion

**Inputs:**
- `ss_benefit`: `20000`
- `agi_excluding_ss`: `20000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`

**Calculation:**
- Provisional income: `20000 + 0 + 10000 = 30000`
- In 50% tier: `0.50 × (30000 − 25000) = 2500`
- Cap: `0.50 × 20000 = 10000` — not hit
- Taxable SS: `2500`

**Expected outputs:**
- `provisional_income`: `30000`
- `taxable_ss`: `2500`
- `inclusion_rate`: `0.1250`
- `tier`: `"fifty_percent"`

---

### Example 3 — Top of 50% Tier, Capped

Ordinary income pushes provisional income to top of 50% tier.
The 50% inclusion cap ($9,600) is less than 50% of benefit ($10,000) so
cap applies.

**Inputs:**
- `ss_benefit`: `20000`
- `agi_excluding_ss`: `30000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`

**Calculation:**
- Provisional income: `30000 + 0 + 10000 = 40000`
- In 50% tier: `0.50 × (40000 − 25000) = 7500`
- Cap: `0.50 × 20000 = 10000` — not hit
- Wait — PI = $40,000 exceeds $34,000 threshold, so this is 85% tier:
  - tier_1_range = 9000, max_tier_1 = min(10000, 4500) = 4500
  - tier_2_amount = 0.85 × (40000 − 34000) = 5100
  - taxable_ss = min(17000, 5100 + 4500) = min(17000, 9600) = 9600

**Expected outputs:**
- `provisional_income`: `40000`
- `taxable_ss`: `9600`
- `inclusion_rate`: `0.4800`
- `tier`: `"eighty_five_percent"`

---

### Example 4 — In 85% Tier, Partial

**Inputs:**
- `ss_benefit`: `20000`
- `agi_excluding_ss`: `35000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`

**Calculation:**
- Provisional income: `35000 + 0 + 10000 = 45000`
- In 85% tier:
  - max_tier_1 = min(10000, 4500) = 4500
  - tier_2_amount = 0.85 × (45000 − 34000) = 9350
  - taxable_ss = min(17000, 9350 + 4500) = min(17000, 13850) = 13850

**Expected outputs:**
- `provisional_income`: `45000`
- `taxable_ss`: `13850`
- `inclusion_rate`: `0.6925`
- `tier`: `"eighty_five_percent"`

---

### Example 5 — Maximum 85% Reached

**Inputs:**
- `ss_benefit`: `20000`
- `agi_excluding_ss`: `50000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`

**Calculation:**
- Provisional income: `50000 + 0 + 10000 = 60000`
- In 85% tier:
  - max_tier_1 = min(10000, 4500) = 4500
  - tier_2_amount = 0.85 × (60000 − 34000) = 22100
  - taxable_ss = min(17000, 22100 + 4500) = min(17000, 26600) = 17000

**Expected outputs:**
- `provisional_income`: `60000`
- `taxable_ss`: `17000`
- `inclusion_rate`: `0.8500`
- `tier`: `"eighty_five_percent"`

---

### Example 6 — Tax-Exempt Interest Increases Provisional Income

Demonstrates that tax-exempt interest (e.g. municipal bond interest) counts toward
provisional income even though it is not included in AGI. This is a planning trap —
muni bond income appears tax-free but can trigger SS taxability.

**Inputs:**
- `ss_benefit`: `20000`
- `agi_excluding_ss`: `18000`
- `tax_exempt_interest`: `5000`
- `filing_status`: `"single"`

**Calculation:**
- Provisional income: `18000 + 5000 + 10000 = 33000`
- In 50% tier: `0.50 × (33000 − 25000) = 4000`
- Cap: `0.50 × 20000 = 10000` — not hit
- Taxable SS: `4000`

**Expected outputs:**
- `provisional_income`: `33000`
- `taxable_ss`: `4000`
- `inclusion_rate`: `0.2000`
- `tier`: `"fifty_percent"`

---

### Example 7 — Zero SS Benefit

**Inputs:**
- `ss_benefit`: `0`
- `agi_excluding_ss`: `50000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`

**Expected outputs:**
- `provisional_income`: `50000`
- `taxable_ss`: `0`
- `inclusion_rate`: `0.0000`
- `tier`: `"none"`

---

## Tax Torpedo Reference Table

SS benefit $24,000, single filer, no tax-exempt interest.
Illustrates how taxable SS increases as ordinary income rises.
Useful for validating the marginal rate service torpedo effect.

| Ordinary Income | Provisional Income | Taxable SS | Inclusion % |
|-----------------|--------------------|------------|-------------|
| $10,000         | $22,000            | $0         | 0.00%       |
| $15,000         | $27,000            | $1,000     | 4.17%       |
| $20,000         | $32,000            | $3,500     | 14.58%      |
| $22,000         | $34,000            | $4,500     | 18.75%      |
| $24,000         | $36,000            | $6,200     | 25.83%      |
| $26,000         | $38,000            | $7,900     | 32.92%      |
| $28,000         | $40,000            | $9,600     | 40.00%      |
| $30,000         | $42,000            | $11,300    | 47.08%      |
| $35,000         | $47,000            | $15,550    | 64.79%      |
| $40,000         | $52,000            | $19,800    | 82.50%      |
| $50,000         | $62,000            | $20,400    | 85.00%      |

> **Note:** The torpedo reference table above should be implemented as a parameterized test
> in `tests/scenarios/` when the marginal rate service is built — not as a standalone SS
> scenario test. The definitive validation of SS taxability behavior is the MER curve: if
> the torpedo spike appears at the correct income range with the correct magnitude, the SS
> service is working correctly end-to-end.

---

## Edge Cases

| Scenario                                     | Expected Behavior                                      |
|----------------------------------------------|--------------------------------------------------------|
| `ss_benefit = 0`                             | `provisional_income` computed normally; `taxable_ss` and `inclusion_rate` are zero; `tier = "none"` |
| `provisional_income` exactly at Tier 1       | `taxable_ss = 0`, `tier = "none"`                      |
| `provisional_income` exactly at Tier 2       | Use 85% tier formula                                   |
| Very high income — taxable SS hits 85% cap   | `taxable_ss = round(0.85 × ss_benefit)`                |
| `tax_exempt_interest > 0`                    | Added to provisional income before threshold comparison|
| `filing_status = "mfj"`                      | Use $32,000 / $44,000 thresholds                       |
| Unsupported `filing_status`                  | Raise `ValueError`                                     |

---

## Out of Scope for This Service

- Federal tax calculation (handled by `federal_tax` service)
- Ohio SS deduction (Ohio exempts SS entirely — handled by `ohio_tax` service)
- NIIT interaction
- State-level SS taxation for states other than Ohio
