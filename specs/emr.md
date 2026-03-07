# Spec: Effective Marginal Rate (EMR) Service

**Version:** 1.0
**Status:** Draft
**Covers:** `services/emr.py`

---

## Purpose

Compute the effective marginal tax rate (EMR) on each incremental dollar of income
across a sweep range. Returns an array of `(income, emr, component_breakdown)` points
suitable for visualization and withdrawal decision support.

The EMR captures all nonlinearities that diverge from the statutory bracket rate:
the Social Security tax torpedo, preferential income stacking, and the NIIT threshold.
Ohio state tax is optionally included as an additive component.
IRMAA thresholds are returned as reference data for visualization but are not included
in the EMR calculation — IRMAA is a Medicare premium, not a tax.

---

## Dependencies

This service composes:
- `services/federal_tax.py` — ordinary and preferential tax calculation
- `services/social_security.py` — SS taxability given provisional income
- `services/ohio_tax.py` — Ohio state tax, included as an optional component

---

## Sweep Modes

The service supports two distinct sweep modes controlled by `sweep_mode`:

**`SweepMode.ORDINARY`** — sweeps `variable_ordinary` (IRA withdrawals, Roth
conversions) while all preferential income is held fixed. Primary use case:
"how much should I withdraw from my IRA this year?"

**`SweepMode.PREFERENTIAL`** — sweeps `variable_preferential` (LTCG harvesting)
while all ordinary income is held fixed. Use case: "how much LTCG can I harvest
before crossing into a higher bracket?"

Both modes return the same output structure. The swept axis is labeled in the
output so the visualization knows what is on the x-axis.

---

## Inputs

### Fixed Income Inputs (all `Decimal`, whole dollar amounts, non-negative)

| Field                  | Description                                              |
|------------------------|----------------------------------------------------------|
| `pension`              | Fixed pension or annuity income                          |
| `interest`             | Taxable interest income                                  |
| `ordinary_dividends`   | Non-qualified (ordinary) dividends                       |
| `inherited_ira_rmd`    | Required minimum distributions from inherited IRA       |
| `ss_benefit`           | Gross Social Security benefit (taxability computed dynamically) |
| `qualified_dividends`  | Qualified dividends (preferential rate) — fixed in ORDINARY mode, fixed component in PREFERENTIAL mode |
| `fixed_ltcg`           | Fixed LTCG already realized — fixed in ORDINARY mode     |
| `tax_exempt_interest`  | Tax-exempt interest (counts toward SS provisional income)|
| `above_the_line_adjustments` | Above-the-line deductions that reduce federal AGI (e.g. HSA contributions). Default `0`. |
| `additional_deductions` | Deductions above the standard deduction (e.g. QBI, excess itemized). Default `0`. |

### Mode and Sweep Inputs

| Field                  | Type         | Default                        | Description                     |
|------------------------|--------------|--------------------------------|---------------------------------|
| `sweep_mode`           | `SweepMode`  | required                       | `ORDINARY` or `PREFERENTIAL`    |
| `variable_ordinary`    | `Decimal`    | `0` (PREFERENTIAL mode only)   | Fixed IRA/Roth amount when sweeping preferential |
| `sweep_floor`          | `Decimal`    | `Decimal('0')`                 | Start of sweep range            |
| `sweep_ceiling`        | `Decimal`    | top of 24% bracket             | End of sweep range              |
| `sweep_step`           | `Decimal`    | `Decimal('100')`               | Increment between sweep points  |
| `filing_status`        | `str`        | required                       | `"single"` or `"mfj"`          |
| `tax_year`             | `int`        | required                       | e.g. `2025`                     |

### Ohio Inputs (all optional)

| Field                       | Type      | Default          | Description                                      |
|-----------------------------|-----------|------------------|--------------------------------------------------|
| `include_ohio`              | `bool`    | `False`          | Whether to compute and include Ohio tax in EMR   |
| `ohio_medical_deduction`    | `Decimal` | `Decimal('0')`   | Pre-computed Ohio medical deduction (fixed, does not adjust dynamically with income — omitting produces a slightly conservative Ohio EMR) |
| `ohio_qualifying_retirement_income` | `Decimal` | `Decimal('0')` | IRA + pension income qualifying for retirement income credit |

When `include_ohio = False`, all `emr_ohio` values are zero and Ohio tax is
excluded from `total_tax` at every sweep point.

The default `sweep_ceiling` is the top of the 24% bracket for the given
`filing_status` and `tax_year`, loaded from bracket data. The caller may
override with any positive `Decimal`.

---

## Outputs

Returns an `EMRResult` dataclass:

| Field              | Type                  | Description                                    |
|--------------------|-----------------------|------------------------------------------------|
| `sweep_mode`       | `SweepMode`           | Mode used for this result                      |
| `points`           | `list[EMRPoint]`      | Sweep array, one entry per income level        |
| `irmaa_thresholds` | `list[Decimal]`       | IRMAA MAGI thresholds for visualization only   |
| `tax_year`         | `int`                 | Tax year used                                  |
| `filing_status`    | `str`                 | Filing status used                             |

### EMRPoint dataclass

| Field                  | Type      | Description                                              |
|------------------------|-----------|----------------------------------------------------------|
| `income`               | `Decimal` | Variable income level at this point                      |
| `total_tax`            | `Decimal` | Total tax at this income level (federal + Ohio if included) |
| `emr`                  | `Decimal` | EMR on next dollar (4 decimal places)                    |
| `emr_ordinary`         | `Decimal` | EMR component: actual marginal ordinary rate (0 below standard deduction) |
| `emr_ss_torpedo`       | `Decimal` | EMR component: additional rate from SS becoming taxable  |
| `emr_pref_stacking`    | `Decimal` | EMR component: additional rate from preferential stacking|
| `emr_niit`             | `Decimal` | EMR component: NIIT rate on preferential income          |
| `emr_ohio`             | `Decimal` | EMR component: Ohio state tax rate (`0` if `include_ohio = False`) |
| `ohio_tax`             | `Decimal` | Ohio tax at this income level (`0` if `include_ohio = False`) |
| `ss_taxable`           | `Decimal` | Taxable SS at this income level                          |
| `ss_inclusion_rate`    | `Decimal` | SS inclusion % at this income level                      |
| `taxable_ordinary`     | `Decimal` | Taxable ordinary income at this income level             |

---

## Calculation Rules

### 1. Fixed Ordinary Income
```
fixed_ordinary = pension + interest + ordinary_dividends + inherited_ira_rmd
```

### 2. Total Ordinary Income at Sweep Point
```
# ORDINARY mode:
total_ordinary = fixed_ordinary + sweep_value

# PREFERENTIAL mode:
total_ordinary = fixed_ordinary + variable_ordinary
```

### 3. Total Preferential Income at Sweep Point
```
# ORDINARY mode:
total_preferential = qualified_dividends + fixed_ltcg

# PREFERENTIAL mode:
total_preferential = qualified_dividends + fixed_ltcg + sweep_value
```

### 4. SS Taxability
At each sweep point, compute provisional income and call `social_security` service:
```
agi_excluding_ss = total_ordinary + total_preferential - above_the_line_adjustments
provisional_income = agi_excluding_ss + tax_exempt_interest + (ss_benefit × 0.50)
```
`above_the_line_adjustments` reduces provisional income — HSA contributions lower
the amount of SS that becomes taxable, which is an important planning interaction.
`ss_taxable` is dynamic — it changes at each sweep point as variable income rises.

### 5. AGI and Taxable Income
```
agi = total_ordinary + ss_taxable + total_preferential - above_the_line_adjustments
taxable_ordinary = max(0, total_ordinary + ss_taxable - standard_deduction - additional_deductions)
```
`above_the_line_adjustments` reduces AGI before SS taxability flows to Ohio.
`additional_deductions` reduces taxable ordinary income below the standard deduction
(e.g. QBI deduction, or excess itemized deductions over the standard deduction amount).
Neither field affects `total_preferential` or the preferential tax calculation.

### 6. Federal Tax
Call `federal_tax` service with:
- `ordinary_income = taxable_ordinary`
- `preferential_income = total_preferential`
- `filing_status`, `tax_year`

### 7. NIIT
```
if agi > niit_threshold:
    niit_base = min(total_preferential, agi - niit_threshold)
    niit = round_tax(niit_base × 0.038)
else:
    niit = 0
```
NIIT threshold: Single $200,000 / MFJ $250,000 (loaded from bracket data).

### 8. Ohio Tax at Sweep Point (optional)

Only computed when `include_ohio = True`. Call `ohio_tax` service with:
- `federal_agi = agi` (computed in step 5)
- `gross_medical_expenses` is not passed — instead `ohio_medical_deduction` is
  applied as a fixed pre-computed deduction
- `qualifying_retirement_income = ohio_qualifying_retirement_income`
- `ss_taxable_federal = ss_taxable`
- `tax_year`

The retirement income credit is applied as configured in `data/ohio_{tax_year}.json`.
It is a fixed step-function credit — it does not change as variable income increases
beyond the $8,000 qualifying retirement income threshold, so it has no marginal
effect on `emr_ohio` in most planning scenarios.

```
ohio_tax = ohio_tax_service.ohio_tax   # after credits
emr_ohio = (ohio_tax(sweep_value + sweep_step) - ohio_tax(sweep_value)) / sweep_step
```

### 9. Total Tax at Sweep Point
```
total_tax = federal_tax.total_tax + niit + ohio_tax
```
Where `ohio_tax = 0` if `include_ohio = False`.

### 10. EMR Calculation
```
emr = (total_tax(sweep_value + sweep_step) - total_tax(sweep_value)) / sweep_step
```
Rounded to 4 decimal places. Computed by calling the full tax calculation
twice — once at `sweep_value`, once at `sweep_value + sweep_step`.

### 11. EMR Component Attribution
Components must sum to `emr` (within rounding tolerance):

**`emr_ordinary`** — actual marginal federal ordinary tax rate at this sweep point. Below the standard deduction (where `taxable_ordinary = 0`), `emr_ordinary = 0` because no federal ordinary tax is owed on the next dollar. At and above the standard deduction, `emr_ordinary` equals the statutory bracket rate at the top dollar of `taxable_ordinary`. This ensures all components reflect actual marginal cost and sum correctly to `emr`.

**`emr_ss_torpedo`** — additional EMR from SS becoming taxable. Non-zero only when
`ss_benefit > 0` and provisional income is in an active torpedo range:
```
emr_ss_torpedo = emr_ordinary × ss_inclusion_rate_delta
```
Where `ss_inclusion_rate_delta` is the change in SS inclusion rate per dollar of
new ordinary income (0.50 in 50% tier, 0.85 in 85% tier, 0 when fully taxed).

**`emr_pref_stacking`** — additional EMR from ordinary income pushing preferential
income into a higher bracket. Non-zero when `total_preferential > 0` and
`taxable_ordinary` is below the preferential bracket ceiling:
```
emr_pref_stacking = preferential_rate_delta × (preferential_pushed / sweep_step)
```
Where `preferential_rate_delta` is the rate difference at the stacking boundary
(e.g. 0.15 when pushing LTCG from 0% to 15%).

**`emr_niit`** — NIIT component. Non-zero only when MAGI crosses or is above the
NIIT threshold:
```
emr_niit = 0.038 × (niit_base_delta / sweep_step)
```

**`emr_ohio`** — Ohio state tax component. Non-zero only when `include_ohio = True`:
```
emr_ohio = (ohio_tax(sweep_value + sweep_step) - ohio_tax(sweep_value)) / sweep_step
```
Approximately 2.75% on most ordinary income after exemption. Steps to 3.125% above
$100,000 Ohio tax base. Zero in the zero-rate bracket (Ohio tax base ≤ $26,050).

### 12. Boundary Point Insertion
In addition to regular `sweep_step` points, the service inserts exact boundary
points at known thresholds to ensure sharp transitions in the visualization:
- Ordinary bracket boundaries (from bracket data)
- Preferential bracket boundaries (from bracket data)
- SS torpedo boundaries (Tier 1 and Tier 2 thresholds)
- SS maximum taxability point (where 85% cap is reached)
- NIIT threshold
- Standard deduction exhaustion point

Boundary points are deduplicated and sorted. The final array is ordered ascending
by `income`.

### 13. IRMAA Reference Thresholds
IRMAA thresholds are loaded from bracket data and returned in `EMRResult.irmaa_thresholds`
as a sorted list of MAGI levels. These are for visualization reference only — vertical
reference lines showing where Medicare premium surcharges would be triggered in the
current planning year. They are not included in any tax calculation.

---

### Net Investment Income Tax (NIIT)

#### Statutory Basis

A flat 3.8% surtax on net investment income (NII) when MAGI exceeds a filing-status
threshold. This is not a bracket — once the threshold is crossed, the surtax applies
to the entire applicable NII amount (not just the excess over the threshold).

#### Thresholds

| Filing Status | Threshold |
|---|---|
| Single / MFS | $200,000 |
| MFJ | $250,000 |

These thresholds have not been inflation-adjusted since NIIT was enacted in 2013.

#### NIIT Base — Net Investment Income

```
niit_base = interest + ordinary_dividends + qualified_dividends + fixed_ltcg + sweep_variable
```

Where `sweep_variable` is:
- In **ORDINARY mode**: the variable ordinary income being swept (IRA/RMD withdrawals
  are ordinary income, not NII — but they increase MAGI, pushing fixed NII into NIIT range)
- In **PREFERENTIAL mode**: the variable preferential income being swept (each additional
  dollar of LTCG is simultaneously NII and MAGI)

**Important:** IRA and RMD withdrawals are ordinary income and do **not** count toward NII.
Only passive investment income (interest, dividends, LTCG) counts. This distinction matters
for the EMR calculation — see interaction with sweep mode below.

#### NIIT Calculation

```
niit = max(0, min(nii, magi - niit_threshold) × 0.038)
```

NIIT applies to the **lesser** of:
- Total net investment income, or
- The amount by which MAGI exceeds the threshold

NIIT is nonzero only when **both** conditions hold: MAGI > threshold AND NII > 0.

#### EMR Impact by Zone

| Zone | `emr_niit` |
|---|---|
| MAGI ≤ threshold | 0 |
| MAGI > threshold, NII fully in NIIT range | 0.038 |
| MAGI crossing threshold | between 0 and 0.038 (transition) |

**ORDINARY sweep mode:** IRA withdrawals increase MAGI but are not NII. Once MAGI
exceeds the threshold, each additional dollar of withdrawal causes more of the fixed NII
(interest, dividends, LTCG) to fall into NIIT range, so `emr_niit` becomes active even
though the variable income itself is not investment income.

**PREFERENTIAL sweep mode:** Each additional dollar of LTCG is both MAGI and NII. Once the
threshold is crossed, `emr_niit = 0.038` stacks on top of the 15%/20% preferential rate,
making the effective rate 18.8% or 23.8% on harvested gains.

#### Interaction with Preferential Stacking

When MAGI crosses $200,000/$250,000 while harvesting LTCG, the EMR jumps by 3.8%. This
is why income ranges that appear to be in the "0% LTCG bracket" are actually subject to
3.8% once total income is high enough to trigger NIIT.

#### Implementation Note

NIIT logic is implemented directly in `services/emr.py` (`_compute_niit_at_point`).
There is no separate `niit.py` service because NIIT has no independent use case outside
the EMR calculation — it is always computed as part of the total tax snapshot.

---

## Worked Examples

---

### Example A — Ordinary Sweep, No SS

**Scenario:** Pension and interest income already in 10% and 12% brackets.
Preferential income will be pushed into 15% rate once ordinary income is high enough.

**Fixed inputs:**
- `pension`: `20000`
- `interest`: `2000`
- `ordinary_dividends`: `0`
- `inherited_ira_rmd`: `0`
- `ss_benefit`: `0`
- `qualified_dividends`: `5000`
- `fixed_ltcg`: `10000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`, `tax_year`: `2025`

**Derived fixed values:**
- `fixed_ordinary`: `22000`
- Standard deduction: `15000`
- At `variable_ordinary = 0`: `taxable_ordinary = 7000` (already in 10% bracket)
- Preferential stacking begins when `taxable_ordinary` reaches `48350`
  (0% LTCG ceiling), i.e. when `variable_ordinary = 41350`

**Selected sweep points:**

| Variable Ordinary | Taxable Ordinary | SS Taxable | Ord Tax | Pref Tax | Total Tax | EMR    |
|-------------------|------------------|------------|---------|----------|-----------|--------|
| `0`               | `7000`           | `0`        | `700`   | `0`      | `700`     | `0.10` |
| `5000`            | `12000`          | `0`        | `1202`  | `0`      | `1202`    | `0.12` |
| `26475`           | `33475`          | `0`        | `3779`  | `19`     | `3798`    | `0.27` |
| `40000`           | `47000`          | `0`        | `5402`  | `2048`   | `7450`    | `0.27` |
| `48350`           | `55350`          | `0`        | `7092`  | `2250`   | `9342`    | `0.22` |
| `100000`          | `107000`         | `0`        | `18528` | `2250`   | `20778`   | `0.24` |

**Key EMR transitions:**
- `variable = 0–4999`: EMR `0.10` — in 10% bracket, no preferential stacking yet
- `variable = 5000–41349`: EMR `0.12` — in 12% bracket
- `variable = 41350–48349`: EMR `0.27` — preferential stacking (12% + 15%)
- `variable = 48350+`: EMR `0.22` — preferential fully in 15% bracket, 22% ordinary bracket
- `variable = 81350+`: EMR `0.24` — 24% bracket

**EMR component breakdown at `variable = 30000`** (in preferential stacking zone):
- `emr_ordinary`: `0.12`
- `emr_ss_torpedo`: `0.00`
- `emr_pref_stacking`: `0.15`
- `emr_niit`: `0.00`
- `emr` total: `0.27`

---

### Example B — Ordinary Sweep, With SS Torpedo

**Scenario:** Fixed income already pushes provisional income above $34,000 Tier 2
threshold before any variable income is added. SS torpedo is active from the start.

**Fixed inputs:**
- `pension`: `15000`
- `interest`: `0`
- `ordinary_dividends`: `0`
- `inherited_ira_rmd`: `8000`
- `ss_benefit`: `24000`
- `qualified_dividends`: `3000`
- `fixed_ltcg`: `5000`
- `tax_exempt_interest`: `0`
- `filing_status`: `"single"`, `tax_year`: `2025`

**Derived fixed values:**
- `fixed_ordinary`: `23000`
- Provisional income at `variable = 0`: `23000 + 8000 + 0 + 12000 = 43000`
  — already in 85% SS tier
- SS taxable at `variable = 0`: `12150` (85% tier formula)
- SS cap (85% × 24000): `20400` — reached at `variable ≈ 10000`

**Selected sweep points:**

| Variable Ordinary | Taxable Ordinary | SS Taxable | Ord Tax | Pref Tax | Total Tax | EMR    |
|-------------------|------------------|------------|---------|----------|-----------|--------|
| `0`               | `20150`          | `12150`    | `2180`  | `0`      | `2180`    | `0.22` |
| `5000`            | `29400`          | `16400`    | `3290`  | `0`      | `3290`    | `0.22` |
| `10000`           | `38400`          | `20400`    | `4370`  | `0`      | `4370`    | `0.12` |
| `15000`           | `43400`          | `20400`    | `4970`  | `458`    | `5428`    | `0.27` |
| `20000`           | `48400`          | `20400`    | `5570`  | `1200`   | `6770`    | `0.15` |
| `25000`           | `53400`          | `20400`    | `6663`  | `1200`   | `7863`    | `0.22` |
| `80000`           | `108400`         | `20400`    | `18864` | `1200`   | `20064`   | `0.24` |

**Key EMR transitions:**
- `variable = 0–9999`: EMR `0.22` — 12% bracket × 1.85 torpedo multiplier
- `variable = 10000+`: EMR drops to `0.12` — SS torpedo exhausted (85% cap reached)
- `variable = 15000–19999`: EMR `0.27` — preferential stacking begins (12% + 15%)
- `variable = 20000–24999`: EMR `0.15` — preferential fully pushed to 15% bracket
- `variable = 25000+`: EMR `0.22` — into 22% ordinary bracket

**EMR component breakdown at `variable = 5000`** (active torpedo, no stacking):
- `emr_ordinary`: `0.12`
- `emr_ss_torpedo`: `0.102` (0.12 × 0.85 inclusion rate delta)
- `emr_pref_stacking`: `0.00`
- `emr_niit`: `0.00`
- `emr` total: `0.222` → rounds to `0.22`

---

### Example C — Preferential Sweep (LTCG Harvesting)

**Scenario:** Ordinary income is fixed. Sweep LTCG to find the 0% harvesting
capacity before the 15% rate applies.

**Fixed inputs:**
- `pension`: `20000`
- `interest`: `0`
- `ordinary_dividends`: `0`
- `inherited_ira_rmd`: `15000`
- `ss_benefit`: `0`
- `qualified_dividends`: `2000`
- `fixed_ltcg`: `0`
- `variable_ordinary`: `0`
- `sweep_mode`: `PREFERENTIAL`
- `filing_status`: `"single"`, `tax_year`: `2025`

**Derived fixed values:**
- `fixed_ordinary`: `35000`
- `taxable_ordinary`: `20000` (35000 − 15000 standard deduction)
- 0% LTCG space: `48350 − 20000 − 2000 = 26350` — LTCG at 0% up to `26350`

**Selected sweep points:**

| Variable LTCG | Taxable Ordinary | Ord Tax | Pref Tax | Total Tax | EMR (pref) |
|---------------|------------------|---------|----------|-----------|------------|
| `0`           | `20000`          | `2162`  | `0`      | `2162`    | `0.00`     |
| `10000`       | `20000`          | `2162`  | `0`      | `2162`    | `0.00`     |
| `20000`       | `20000`          | `2162`  | `0`      | `2162`    | `0.00`     |
| `26350`       | `20000`          | `2162`  | `0`      | `2162`    | `0.15`     |
| `30000`       | `20000`          | `2162`  | `548`    | `2710`    | `0.15`     |
| `40000`       | `20000`          | `2162`  | `2048`   | `4210`    | `0.15`     |
| `50000`       | `20000`          | `2162`  | `3548`   | `5710`    | `0.15`     |

**Key EMR transition:**
- `variable_ltcg = 0–26349`: EMR `0.00` — LTCG in 0% bracket
- `variable_ltcg = 26350+`: EMR `0.15` — LTCG in 15% bracket

**Planning insight:** Up to `$26,350` of LTCG can be harvested this year at 0%
federal tax. The exact boundary point `26350` must appear as an explicit point
in the output array (boundary insertion rule).

---

## Edge Cases

| Scenario                                          | Expected Behavior                                         |
|---------------------------------------------------|-----------------------------------------------------------|
| `ss_benefit = 0`                                  | `emr_ss_torpedo = 0` at all points                        |
| All preferential income = 0                       | `emr_pref_stacking = 0` at all points                     |
| Fixed income already past SS 85% cap              | `emr_ss_torpedo = 0` from sweep start                     |
| `sweep_floor = sweep_ceiling`                     | Return single-point array                                 |
| `sweep_ceiling` overridden below default          | Respect caller value, do not extend to default            |
| `include_ohio = False`                            | `emr_ohio = 0`, `ohio_tax = 0` at all points              |
| `include_ohio = True`, `ohio_medical_deduction = 0` | Ohio EMR slightly overstated — documented simplification |
| Unsupported `tax_year` or `filing_status`         | Raise `ValueError`                                        |
| `sweep_step` larger than sweep range              | Return boundary points only                               |

---

## Out of Scope for This Service

- IRMAA surcharge calculation (thresholds returned as reference data only)
- ACA premium subsidy interactions
- Two-dimensional sweep (varying both ordinary and preferential simultaneously)
- Other state income tax (Ohio only)
- AMT
