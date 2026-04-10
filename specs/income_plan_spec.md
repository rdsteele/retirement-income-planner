# Income Plan Service Specification

## Purpose

The `income_plan` service is the authoritative home for income planning business
logic. It replaces the MAGI computation and payload-assembly code that previously
lived as JavaScript in `income.html`, making that logic:

- Testable in isolation
- Correct for both Single and MFJ filers (the prior JS approximation only
  handled Single filers)
- Consistent: the live Plan Summary and the full EMR sweep use the same formula

---

## Service: `services/income_plan.py`

### Function 1: `classify_withdrawals`

```python
def classify_withdrawals(
    planned: list[PlannedWithdrawal],
    executed: list[ExecutedWithdrawal],
) -> WithdrawalTotals
```

Classifies planned and executed withdrawals into ordinary / preferential income
categories. Pure function — no I/O, no external dependencies.

#### Planned withdrawal types

| `account_type`  | Income treatment                                        |
|-----------------|---------------------------------------------------------|
| `taxable`       | `gain = max(0, amount - min(basis, amount))` → preferential (LTCG); basis portion is MAGI-neutral return-of-capital |
| `traditional`   | Full amount → ordinary income                           |
| `roth`          | MAGI-neutral — excluded from all income totals          |
| `hsa`           | MAGI-neutral — excluded from all income totals          |

**Basis cap rule:** When `basis > amount` for a taxable withdrawal (impossible in
normal use, but guarded against), effective basis is capped at `amount`. You cannot
recover more cost basis than the amount withdrawn.

#### Executed withdrawal types

| `withdrawal_type`  | Income treatment                                       |
|--------------------|--------------------------------------------------------|
| `ltcg`             | `gain = max(0, amount - basis)` → preferential; basis is return-of-capital |
| `stcg`             | `gain = max(0, amount - basis)` → ordinary income; basis is return-of-capital |
| `tax_deferred`     | Full amount → ordinary income                          |
| `tax_free_roth`    | MAGI-neutral                                           |
| `tax_free_hsa`     | MAGI-neutral                                           |

---

### Function 2: `compute_plan_summary`

```python
def compute_plan_summary(
    *,
    filing_status: str,
    pension: Decimal,
    pension_taxable: Decimal,
    interest: Decimal,
    ordinary_dividends: Decimal,
    ira_distributions: Decimal,
    ss_benefit: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    above_the_line_adjustments: Decimal,
    tax_exempt_interest: Decimal,
    essential_spending: Decimal,
    discretionary_spending: Decimal,
    aca_cliff_magi: Decimal,
    estimated_taxes: Decimal,
    planned: list[PlannedWithdrawal],
    executed: list[ExecutedWithdrawal],
) -> PlanSummary
```

Computes a live plan summary without running the full EMR sweep. Called on every
form blur event in `income.html` via `POST /api/income-plan/summary`.

#### MAGI computation

```
AGI (excl. SS) =
    pension_taxable + interest + ordinary_dividends + ira_distributions
  + qualified_dividends + fixed_ltcg
  + traditional_withdrawals + taxable_gains
  + exec_ordinary + exec_preferential
  - above_the_line_adjustments

Provisional Income =
    AGI (excl. SS) + tax_exempt_interest + 0.50 × ss_benefit

SS Taxability → calculate_social_security_taxability(ss_benefit, AGI_excl_SS,
                    tax_exempt_interest, filing_status)

MAGI =
    AGI (excl. SS) + ss_taxable + tax_exempt_interest
```

ACA MAGI matches the definition used in `services/total_cost.py`.

#### SS taxability method

`compute_plan_summary` calls `calculate_social_security_taxability` from
`services/social_security.py` — the same function used in the full EMR sweep.
This is correct for both Single and MFJ filers. The prior JavaScript
approximation applied only Single filer thresholds ($25,000 / $34,000) regardless
of filing status.

#### Shortfall computation

```
total_spending = essential_spending + discretionary_spending
total_expenses = total_spending + above_the_line_adjustments + estimated_taxes

gross_forced_income =
    pension + interest + ordinary_dividends + ira_distributions
  + qualified_dividends + fixed_ltcg + ss_benefit   ← gross amounts (pension gross, not taxable)

shortfall = total_expenses - gross_forced_income - total_all_withdrawals
```

`shortfall` is `None` when both `total_spending` and `estimated_taxes` are zero
(nothing entered yet — avoids displaying a meaningless $0 shortfall on load).

A negative shortfall is a surplus.

#### ACA distance

```
aca_distance = aca_cliff_magi - magi
```

`aca_distance` is `None` when `aca_cliff_magi` is zero. `aca_cliff_magi` is zero
on page load and is populated from the last Calculate response. It is passed back
to the summary endpoint by the UI on each subsequent call.

---

### Function 3: `assemble_sweep_inputs`

```python
def assemble_sweep_inputs(
    *,
    pension_taxable, interest, ordinary_dividends, ira_distributions,
    ss_benefit, qualified_dividends, fixed_ltcg,
    above_the_line_adjustments, tax_exempt_interest,
    planned: list[PlannedWithdrawal],
    executed: list[ExecutedWithdrawal],
) -> dict[str, Decimal]
```

Merges withdrawal totals into the forced-income fields required by
`calculate_total_cost`. Returns a dict ready to `**`-unpack into the service call.

#### Merge rules

```
ira_distributions (augmented) =
    ira_distributions
  + traditional_withdrawals        # planned traditional
  + exec_ordinary                  # executed tax_deferred + STCG gains

fixed_ltcg (augmented) =
    fixed_ltcg
  + taxable_gains                  # planned taxable holding gains
  + exec_preferential              # executed LTCG gains
```

Roth and HSA withdrawals are not merged into any income field — they are
MAGI-neutral and do not affect the EMR sweep.

---

## API Endpoints

### `POST /api/income-plan/summary`

Live plan summary. Called on every `focusout` event in `income.html`
(debounced 150 ms). Does not run the EMR sweep.

**Request:** `IncomePlanRequest` (sweep fields are present but ignored)

**Response:** `PlanSummaryResponse`

```json
{
  "magi": 45230,
  "forced_ordinary": 38000,
  "forced_preferential": 5000,
  "withdrawal_ordinary": 15000,
  "withdrawal_preferential": 3800,
  "executed_ordinary": 0,
  "executed_preferential": 0,
  "ss_taxable": 7230,
  "provisional_income": 32000,
  "total_spending": 60000,
  "total_income": 61800,
  "shortfall": null,
  "aca_distance": 17370,
  "aca_cliff_magi": 62600,
  "total_taxable_withdrawals": 8800,
  "total_traditional_withdrawals": 15000,
  "total_roth_withdrawals": 0,
  "total_hsa_withdrawals": 0,
  "total_pension_annuity": 12000,
  "total_ss_benefit": 24000,
  "total_all_withdrawals": 59800
}
```

`shortfall` is `null` when no spending is entered.
`aca_distance` is `null` when `aca_cliff_magi` is `0`.

### `POST /api/income-plan/calculate`

Full EMR sweep for an income plan. Called when the user clicks Calculate.
Assembles augmented sweep inputs (merging withdrawal totals) then delegates to
`calculate_total_cost`. Returns the same `TotalCostResponse` as `/api/total-cost`.

**Request:** `IncomePlanRequest` (sweep fields are used)

**Response:** `TotalCostResponse` (identical schema to `/api/total-cost`)

The sweep is always run in `ordinary` mode with the full withdrawal mix baked in.
`/api/total-cost` remains available for direct use (e.g., `emr.html`).

---

## Request Model: `IncomePlanRequest`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `filing_status` | str | required | `"single"` or `"mfj"` |
| `tax_year` | int | required | |
| `pension` | float ≥ 0 | 0 | Gross pension/annuity payment (1040 line 5a) |
| `pension_taxable` | float ≥ 0 | 0 | Taxable portion (1040 line 5b) |
| `interest` | float ≥ 0 | 0 | |
| `ordinary_dividends` | float ≥ 0 | 0 | |
| `ira_distributions` | float ≥ 0 | 0 | Fixed IRA distributions (not including withdrawals) |
| `ss_benefit` | float ≥ 0 | 0 | Annual gross benefit |
| `qualified_dividends` | float ≥ 0 | 0 | |
| `fixed_ltcg` | float ≥ 0 | 0 | Fixed LTCG (not including withdrawal gains) |
| `tax_exempt_interest` | float ≥ 0 | 0 | Added to ACA MAGI |
| `above_the_line_adjustments` | float ≥ 0 | 0 | e.g., HSA contribution |
| `additional_deductions` | float ≥ 0 | 0 | Beyond standard deduction (e.g. QBI, excess itemized); passed through to `calculate_total_cost` |
| `essential_spending` | float ≥ 0 | 0 | |
| `discretionary_spending` | float ≥ 0 | 0 | |
| `include_aca` | bool | false | |
| `aca_cliff_magi` | float ≥ 0 | 0 | Pass-through from last Calculate response |
| `estimated_taxes` | float ≥ 0 | 0 | Pass-through from last Calculate response |
| `planned_withdrawals` | list | [] | See `PlannedWithdrawalRequest` |
| `executed_withdrawals` | list | [] | See `ExecutedWithdrawalRequest` |
| `sweep_floor` | float ≥ 0 | 0 | Calculate endpoint only |
| `sweep_ceiling` | float > 0 | 150000 | Calculate endpoint only |
| `sweep_step` | float > 0 | 100 | Calculate endpoint only |
| `include_ohio` | bool | true | Calculate endpoint only |
| `ohio_medical_deduction` | float ≥ 0 | 0 | Calculate endpoint only |
| `ohio_qualifying_retirement_income` | float ≥ 0 | 0 | Calculate endpoint only |
| `aptc_monthly` | float ≥ 0 | 0 | Calculate endpoint only |
| `silver_premium_monthly` | float ≥ 0 | 0 | Calculate endpoint only |

---

## Withdrawal Type Taxonomy

### `PlannedWithdrawalRequest.account_type`

| Value | Description |
|-------|-------------|
| `taxable` | Brokerage / taxable account holding |
| `traditional` | Traditional IRA, 401(k), 403(b) |
| `roth` | Roth IRA, Roth 401(k) |
| `hsa` | Health Savings Account (qualified medical withdrawals) |

### `ExecutedWithdrawalRequest.withdrawal_type`

| Value | Description |
|-------|-------------|
| `ltcg` | Long-term capital gain from taxable account |
| `stcg` | Short-term capital gain from taxable account (ordinary) |
| `tax_deferred` | Traditional IRA / 401(k) distribution |
| `tax_free_roth` | Roth IRA qualified distribution |
| `tax_free_hsa` | HSA qualified medical distribution |

---

## UI Contract (`income.html`)

After this refactor, `income.html` JS:

1. **On `focusout`** (debounced 150 ms): calls `POST /api/income-plan/summary`
   with current form values and renders `PlanSummaryResponse` into the Plan
   Summary card. No formulas in JS.

2. **On Calculate click**: calls `POST /api/income-plan/calculate` with raw form
   values (including withdrawal arrays). The service merges withdrawal totals
   into forced-income fields internally. JS receives `TotalCostResponse` and
   renders chart + key points exactly as before.

3. **`acaCliffMagi` state**: starts at `0`, updated from `lastResult.aca_cliff_magi`
   after each Calculate. Passed to the summary endpoint so ACA distance can be
   computed on subsequent blur events.

4. **`estimatedTaxes` state**: starts at `0`, updated from
   `lastResult.points.total_tax[0]` after each Calculate. Passed to the summary
   endpoint. Shown as `—` in the UI when `taxesStale` is true.
