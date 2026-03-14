# Spec: Income Planning Frontend

**Version:** 1.0
**Status:** Draft
**Covers:** `api/static/income.html`, nav bar addition to `api/static/index.html`

---

## Purpose

Annual retirement income planning tool. The user enters a spending goal, forced
income, and withdrawal mix across account types, and sees the resulting MAGI,
ACA cliff proximity, total cost EMR chart, and portfolio summary. The page
consumes the account inventory and total cost API endpoints.

This page is complementary to the EMR Analysis page (`index.html`). The EMR page
is a standalone analytical tool for sweeping a single variable. The income planning
page is oriented toward a specific year's plan with actual account balances,
spending targets, and a concrete withdrawal mix.

---

## Serving

Same static mount as `index.html`. Accessible at:
```
http://localhost:8000/static/income.html
```

---

## Navigation Bar

A top nav bar is added to both `index.html` (existing) and `income.html` (new).

```
[ Retirement Income Planner ]    EMR Analysis  |  Income Planning
```

- "EMR Analysis" links to `/static/index.html`
- "Income Planning" links to `/static/income.html`
- The active page link is visually distinguished (underline or highlight)
- Nav bar is consistent in style and position across both pages

---

## Layout

Two-column layout: left panel (inputs), right panel (outputs).
On narrow screens columns stack vertically (left above right).
Max page width: `1200px`, centered.

---

## Left Panel — Inputs

### Data Loading on Page Load

On page load, two API calls are made in parallel:
- `GET /api/accounts` — populates the Withdrawal Mix section
- `GET /api/accounts/summary` — pre-fills HSA contribution field

If either call fails, display an inline error in the relevant section and
allow manual entry to proceed.

---

### Section: Income Needs

| Label | Field | Notes |
|---|---|---|
| Essential Spending | `essential_spending` | Housing, food, medical, insurance |
| Discretionary Spending | `discretionary_spending` | Travel, hobbies, etc. |
| **Total Spending** | derived display | `essential + discretionary`, updated live |

---

### Section: Forced Income

Income that arrives regardless of withdrawal decisions.

| Label | Field | Notes |
|---|---|---|
| Pension | `pension` | |
| Interest | `interest` | Bank, brokerage, bonds — all taxable interest |
| Ordinary Dividends | `ordinary_dividends` | Includes qualified dividends as a subset |
| Qualified Dividends | `qualified_dividends` | Subset of ordinary dividends, preferential rate |
| RMDs | `rmds` | Required minimum distributions from tax-deferred accounts |
| Social Security Benefit | `ss_benefit` | Gross annual SS benefit; taxability is calculated |
| Fixed LTCG | `fixed_ltcg` | Known capital gain distributions or forced sales |

---

### Section: Adjustments

| Label | Field | Notes |
|---|---|---|
| HSA Contribution | `hsa_contribution` | Above-the-line deduction; pre-filled from `GET /api/accounts/summary` `hsa_annual_contribution` if present; editable override |

---

### Section: ACA

| Label | Field | Notes |
|---|---|---|
| Monthly APTC | `aptc_monthly` | Advance premium tax credit from marketplace enrollment |
| Monthly Plan Premium | `silver_premium_monthly` | Second-lowest-cost silver plan (SLCSP) monthly premium |

---

### Section: Withdrawal Mix

Populated dynamically from `GET /api/accounts` on page load. Accounts are
displayed in this order: taxable, tax-deferred, Roth, HSA.

If no accounts are present, display a message: "No accounts found. Add accounts
to enable withdrawal mix inputs." with a note that account management is not
yet available in the UI (data must be added to `data/accounts.json` directly).

#### Taxable Accounts

For each taxable account, display the account name as a subheader.
For each holding within the account:

| Column | Notes |
|---|---|
| Ticker | Display only (from inventory) |
| Basis | Display only |
| Value | Display only |
| Unrealized Gain | Display only (`value - basis`) |
| Withdraw ($) | Input — dollar amount to withdraw from this holding |
| Basis Portion ($) | Auto-calculated: `withdraw × (basis / value)`, editable override |
| Gain ($) | Derived display: `withdraw - basis_portion` |

Auto-calculation of basis portion fires on change of the withdraw input.
If the user edits basis portion directly, it becomes a manual override and
is no longer auto-updated when the withdraw amount changes.
Gain is always `withdraw - basis_portion` and is display-only.

#### Tax-Deferred Accounts

For each traditional account, display account name and balance (read-only).
Single input:

| Label | Field | Notes |
|---|---|---|
| Withdrawal / Conversion ($) | `trad_withdrawal_{account_id}` | Adds to MAGI as ordinary income |

#### Roth Accounts

For each Roth account, display account name and balance (read-only).
Single input:

| Label | Field | Notes |
|---|---|---|
| Withdrawal ($) | `roth_withdrawal_{account_id}` | MAGI-neutral; funds spending |

#### HSA Accounts

For each HSA account, display account name and balance (read-only).
No withdrawal input — HSA balance is informational only on this page.
Contribution is captured in the Adjustments section.

---

## Right Panel — Outputs

All output sections update on "Calculate" button click, except the MAGI
Summary card which updates live as inputs change.

---

### Section: MAGI Summary Card

Updates live (no API call) as any input changes.

**MAGI Calculation (client-side approximation):**

```
total_gain_withdrawals   = sum(gain portion from all taxable holdings)
total_trad_withdrawals   = sum(trad withdrawal amounts)

provisional_income       = pension + interest + ordinary_dividends + rmds
                         + fixed_ltcg + total_gain_withdrawals
                         + total_trad_withdrawals
                         - hsa_contribution
                         + (ss_benefit × 0.50)

ss_taxable_approx        = approximate_ss_taxable(ss_benefit, provisional_income)

magi                     = pension + interest + ordinary_dividends + rmds
                         + fixed_ltcg + total_gain_withdrawals
                         + total_trad_withdrawals
                         + ss_taxable_approx
                         - hsa_contribution
```

SS taxability approximation (single filer, for live display only — exact
calculation is performed server-side):
```javascript
function approximate_ss_taxable(ss_benefit, provisional_income) {
    if (ss_benefit === 0) return 0;
    const tier1 = Math.max(0, Math.min(provisional_income - 25000, 9000));
    const tier2 = Math.max(0, provisional_income - 34000);
    const included = Math.min(tier1 * 0.50 + tier2 * 0.85, ss_benefit * 0.85);
    return Math.max(0, included);
}
```

Note: This approximation uses single-filer thresholds and is sufficient for
live display. The accurate SS taxability is computed server-side via the
social security service when Calculate is clicked.

**Display fields:**

| Field | Notes |
|---|---|
| Projected MAGI | Formatted as `$XX,XXX` |
| ACA Cliff | `$62,600` (2026 single, hardcoded for now) |
| Distance to Cliff | `cliff - magi`; formatted as `$X,XXX under` or `$X,XXX OVER` |
| Basis Withdrawals | Sum of all basis portions across taxable holdings (MAGI-neutral) |
| Roth Withdrawals | Sum of all Roth withdrawal inputs (MAGI-neutral) |
| Total Spending | `essential + discretionary` |
| Shortfall | `total_spending - forced_income - basis_withdrawals` |

**Status color on Distance to Cliff:**
- Green: more than $5,000 under cliff
- Yellow: $0–$5,000 under cliff
- Red: over cliff

**Shortfall note:** A positive shortfall means the spending gap must be funded
by taxable gains, tax-deferred withdrawals, or Roth withdrawals (all captured
in the withdrawal mix). A negative shortfall means forced income + basis
withdrawals exceed spending (surplus).

---

### Section: Total Cost EMR Chart

Rendered on "Calculate" button click via `POST /api/total-cost`.

**Request payload built from inputs:**
```javascript
{
  pension:                  pension,
  interest:                 interest,
  ordinary_dividends:       ordinary_dividends,
  inherited_ira_rmd:        rmds,
  ss_benefit:               ss_benefit,
  qualified_dividends:      qualified_dividends,
  fixed_ltcg:               fixed_ltcg,
  above_the_line_adjustments: hsa_contribution,
  sweep_mode:               "ordinary",
  filing_status:            "single",
  tax_year:                 2026,
  sweep_floor:              0,
  sweep_ceiling:            150000,
  sweep_step:               100,
  include_ohio:             true,
  include_aca:              true,
  aptc_monthly:             aptc_monthly,
  silver_premium_monthly:   silver_premium_monthly
}
```

Note: `rmds` maps to `inherited_ira_rmd` in the API request (field name
mismatch between the income planning UI and the underlying EMR service).

**Chart configuration:**

Same Plotly patterns as `index.html` (stacked area default, lines toggle,
same color scheme). Add:

- Vertical annotation line at `planning_signals.aca_cliff_sweep_value`
  with label `"ACA Cliff $XX,XXX"` (formatted with comma separator)
- The ACA `emr_aca` component is **not** rendered as a stacked area trace
  (the spike would exceed the y-axis cap and compress the useful range)
- x-axis label: `"Additional Ordinary Income ($)"` (sweep_mode is always
  ORDINARY on this page)
- y-axis cap: `CONFIG.yAxisMaxEMR = 0.50` (same as `index.html`)

**Button behavior:**
- "Calculate" button disabled while request is in flight; text changes to "Calculating..."
- HTTP 422: display `detail` field below button in red
- HTTP 500: display generic error message in red
- Network error: display "Could not reach the server. Is the API running?" in red
- Clear previous error on each new click

---

### Section: Key Points Table

Rendered below the chart after a successful Calculate. Built from
`planning_signals` in the API response.

| Column | Notes |
|---|---|
| Income Level | `sweep_value` formatted as `$XX,XXX` |
| Marginal Rate | `rate` formatted as `XX.X%` |
| Notes | Description of the transition |

Rows:
- Zero-rate threshold (`zero_rate_threshold`): "Standard deduction exhausted"
- Each entry in `bracket_boundaries`: bracket boundary notes from API
- ACA cliff (`aca_cliff_sweep_value`): "ACA cliff — full APTC lost"

If `include_aca = true` and no ACA cliff row is present (cliff is beyond sweep
ceiling), display a note: "ACA cliff is beyond the sweep range."

---

### Section: Portfolio Summary

Rendered from `GET /api/accounts/summary` on page load. Refreshed after
each Calculate click.

| Row | Value |
|---|---|
| Taxable Value | `$XXX,XXX` |
| Taxable Basis | `$XXX,XXX` |
| Taxable Unrealized Gain | `$XXX,XXX` |
| Tax-Deferred Balance | `$XXX,XXX` |
| Roth Balance | `$XXX,XXX` |
| HSA Balance | `$XXX,XXX` |
| **Total Portfolio** | `$XXX,XXX` |

---

## External Dependencies

Same Plotly local reference as `index.html`:
```html
<script src="/static/plotly-2.26.0.min.js"></script>
```

No other external dependencies. All styling inline or in a `<style>` block
in the same file.

---

## Styling

Consistent with `index.html`.
- Background: `#f8f9fa` (light gray page), `#ffffff` (white cards)
- Font: system font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`)
- Max page width: `1200px`, centered (wider than EMR page to accommodate two columns)
- Status card colors: green `#16a34a`, yellow `#d97706`, red `#dc2626`
- Chart container: white card with subtle shadow
- Holding rows in withdrawal mix: subtle alternating row background for readability

---

## Out of Scope

- Account management UI (accounts are managed via `data/accounts.json` directly)
- Save / load income plan to file
- Multi-year projection
- Solver (auto-optimize withdrawal mix given spending goal)
- MFJ filing status (single filer only for now)
- Tax year selection (2026 hardcoded)
- IRMAA display
- Print / export
