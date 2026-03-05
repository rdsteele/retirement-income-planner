# Services Layer — Tax Domain Knowledge

This file documents tax concepts that are not obvious from code alone. Read this before
modifying any service module.

---

## Preferential Income Stacking Order

The IRS taxes income in a specific stacking order. Ordinary income sits at the bottom of
the stack; preferential income (LTCG and qualified dividends) stacks on top. This means:

1. **Ordinary income** fills the bottom brackets first:
   wages, IRA distributions, pension, annuity, taxable Social Security,
   short-term capital gains, ordinary dividends, taxable interest

2. **Preferential income** (LTCG + qualified dividends) stacks on top of ordinary income
   and is taxed using its own bracket schedule (0% / 15% / 20%)

**Why this matters:** The LTCG bracket thresholds are based on *total* taxable income, not
just LTCG income. To determine which LTCG rate applies, you must know where ordinary income
ends and where LTCG begins on the combined income stack. Always calculate ordinary income
taxes first, then determine where preferential income sits within the LTCG brackets.

---

## Social Security Taxability — Provisional Income

Social Security benefits are not fully taxable. The taxable portion is determined by
**provisional income**:

```
Provisional Income = AGI (excluding SS) + tax-exempt interest + 50% of SS benefit
```

Taxability tiers (single filer):

| Provisional Income      | Taxable SS Portion         |
|-------------------------|----------------------------|
| Below $25,000           | 0%                         |
| $25,000 – $34,000       | Up to 50% of benefit       |
| Above $34,000           | Up to 85% of benefit       |

MFJ thresholds are $32,000 and $44,000 respectively.

The maximum taxable SS benefit is **85%** — never 100%.

---

## The Tax Torpedo (SS Torpedo)

In the provisional income range where Social Security becomes taxable, each additional
dollar of ordinary income causes *more than one dollar* of income to be taxed:

- $1 of new ordinary income increases AGI by $1
- This increases provisional income, pulling more SS into taxable income
- In the 50% inclusion tier: each $1 of new income effectively taxes $1.50
- In the 85% inclusion tier: each $1 of new income effectively taxes $1.85

This creates a pronounced spike in the marginal effective tax rate (MER) — visually
dramatic on a MER curve graph. This effect is one of the primary planning insights
this tool is designed to reveal.

---

## Marginal Effective Tax Rate (MER)

The MER is the tax rate on the *next dollar* of a specific income type. It is **not**
the same as the marginal bracket rate because multiple tax effects interact:

- Ordinary income bracket rate
- Additional SS becoming taxable (the torpedo effect)
- LTCG rate shifting as ordinary income pushes preferential income into higher brackets
- NIIT threshold crossover

**Calculation approach:** Compute total tax at income X, then at income X + $1 (or a
small increment for smoothing). The MER = (tax(X+1) - tax(X)) / 1.

The MER curve — plotting MER as one income source varies — is the primary planning
visualization. It reveals the torpedo zone, bracket crossovers, and optimal
income ranges at a glance.

---

## Net Investment Income Tax (NIIT)

A flat **3.8% surtax** on net investment income (interest, dividends, LTCG, rental income)
for taxpayers above the MAGI threshold:

- Single: $200,000
- MFJ: $250,000

NIIT applies to the *lesser* of net investment income or the amount by which MAGI exceeds
the threshold. It is calculated independently and added on top of regular income tax.
It appears as a discrete jump in the MER curve at the threshold.

---

## EMR Component Attribution Bias

When the SS torpedo is active, the sum of EMR components (`emr_ordinary + emr_ss_torpedo +
emr_pref_stacking + emr_niit + emr_ohio`) diverges from `emr` by approximately **0.002**.
This is structural, not a bug to fix.

**Cause:** `emr_ordinary` is assigned the statutory bracket rate analytically (e.g. `0.12`),
but the actual ordinary tax delta is computed per-bracket with `round_tax()` in
`federal_tax.py`. When the torpedo is active, `taxable_ordinary` changes by a non-integer
multiple of `sweep_step` (e.g. 1.85×), causing per-bracket rounding to produce a tax delta
that differs from `bracket_rate × Δtaxable_ordinary` by up to $1. Over a $100 step this
yields a ~0.002 rate discrepancy. The bias is persistent at every torpedo-active sweep point,
not just at bracket boundaries.

---

## Filing Status

All bracket thresholds and SS provisional income thresholds vary by filing status.
Filing status must be a first-class input to every service that applies brackets.
Supported statuses: Single, Married Filing Jointly (MFJ), Married Filing Separately (MFS).

---

## Tax Year

Bracket amounts adjust annually for inflation. Tax year must be a first-class input.
Bracket data is loaded from `data/brackets/federal_{year}.json`. Never hardcode bracket
amounts in service code — always load from the data layer.
