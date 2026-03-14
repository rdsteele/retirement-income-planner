# Spec: Tax Detail Frontend

**Version:** 1.0
**Status:** Draft
**Covers:** `api/static/tax.html`

---

## Purpose

Point-in-time tax calculator showing a complete federal and Ohio tax breakdown
for a given set of income inputs. Mirrors the structure of a manual tax
spreadsheet — income flows through adjustments to AGI, then through bracket
tables to a final tax bill. Recalculates automatically when any input field
loses focus.

This page is complementary to the EMR Analysis page. The EMR page shows how
marginal rates change across a sweep range. The tax detail page shows the exact
tax bill at a specific income level with full bracket transparency.

---

## Serving

Same static mount as `index.html`. Accessible at:
```
http://localhost:8000/static/tax.html
```

---

## Navigation Bar

Same nav bar as `index.html` and `income.html`:

```
[ Retirement Income Planner ]    EMR Analysis  |  Tax Detail  |  Income Planning
```

- "EMR Analysis" links to `/static/index.html`
- "Tax Detail" links to `/static/tax.html`
- "Income Planning" links to `/static/income.html`
- Active page visually distinguished
- Nav bar added to all three pages (`index.html`, `tax.html`, `income.html`)

---

## Layout

Two-column layout: left panel (inputs), right panel (outputs).
Same pattern as `index.html`.
Max page width: `1200px`, centered.

---

## Left Panel — Inputs

All fields are numeric inputs, `min="0"`, `step="1"`.
Empty fields treated as `0` when building the request payload.
Calculation fires on `blur` event of any input field, and on page load.

### Section: Income

| Label | Field | Notes |
|---|---|---|
| Wages | `wages` | W-2 wages |
| Pension / Annuity | `pension` | Taxable pension and annuity income |
| Taxable Interest | `interest` | Bank, brokerage, bonds |
| Ordinary Dividends | `ordinary_dividends` | Includes qualified dividends as subset |
| Qualified Dividends | `qualified_dividends` | Subset of ordinary dividends |
| IRA Distributions / RMDs | `ira_distributions` | Taxable IRA/401k withdrawals, RMDs, Roth conversions |
| Social Security Benefit | `ss_benefit` | Gross annual SS benefit; taxability calculated |
| Capital Gains (LT) | `fixed_ltcg` | Long-term capital gains |
| Tax-Exempt Interest | `tax_exempt_interest` | Municipal bond interest etc. |

### Section: Adjustments

| Label | Field | Notes |
|---|---|---|
| Above-the-Line Adjustments | `above_the_line_adjustments` | HSA contributions, IRA deductions, etc. |
| Additional Deductions | `additional_deductions` | QBI deduction, excess itemized deductions |

### Section: Settings

| Label | Field | Type | Notes |
|---|---|---|---|
| Filing Status | `filing_status` | select | `single` (default), `mfj` |
| Tax Year | `tax_year` | select | Populated from `GET /api/tax-years`; default = highest year |
| Include Ohio | `include_ohio` | checkbox | unchecked by default |

**Ohio sub-fields** (shown only when Include Ohio is checked):

| Label | Field | Notes |
|---|---|---|
| Gross Medical Expenses | `gross_medical_expenses` | Before 7.5% AGI floor |
| Qualifying Retirement Income | `ohio_qualifying_retirement_income` | IRA + pension for retirement credit |

---

## Calculation Trigger

Calculation fires on:
- `blur` event on any input field or settings change
- Page load (using default/zero values)
- Tax year dropdown populated from API (fires once on load)

No explicit "Calculate" button. Output updates automatically when focus leaves
any field.

While a request is in flight, show a subtle loading indicator on the output
panel (e.g. reduced opacity). Do not disable inputs.

---

## Right Panel — Outputs

All output sections update together after each API response.
Hidden on initial page load until the first successful response.

---

### Section: Inputs Summary

Displayed as a vertical list of labeled values — the "bridge" between raw
inputs and the bracket tables. Shows how gross income flows to taxable income.

| Label | Value | Notes |
|---|---|---|
| Gross Ordinary Income | `$XX,XXX` | pension + interest + ordinary_dividends + ira_distributions + wages |
| Social Security Taxable | `$XX,XXX` | Computed by SS service |
| Above-the-Line Adjustments | `($XX,XXX)` | Shown as negative |
| **AGI** | `$XX,XXX` | Bold |
| Standard Deduction | `($XX,XXX)` | Shown as negative |
| Additional Deductions | `($XX,XXX)` | Shown as negative; hidden if zero |
| **Taxable Income (Ordinary)** | `$XX,XXX` | Bold |
| **Taxable Income (Preferential)** | `$XX,XXX` | Bold |

---

### Section: Federal Tax

#### Ordinary Income Brackets

Table with columns: Rate | From | To | Income Taxed | Tax Amount

Only show brackets where `income_taxed > 0` OR the first bracket (always
show at least one row). Highlight the row containing the top dollar of
ordinary income (the marginal bracket).

| Rate | From | To | Income Taxed | Tax Amount |
|---|---|---|---|---|
| 10% | $0 | $12,400 | $X,XXX | $XXX |
| 12% | $12,401 | $50,400 | $X,XXX | $X,XXX |

Row below table: **Ordinary Tax Total: $X,XXX**

#### Preferential Income Brackets (Capital Gains)

Same table structure. Only shown when `taxable_preferential > 0`.

| Rate | From | To | Income Taxed | Tax Amount |
|---|---|---|---|---|
| 0% | $0 | $49,450 | $XX,XXX | $0 |
| 15% | $49,451 | $545,500 | $X,XXX | $XXX |

Row below table: **Preferential Tax Total: $X,XXX**

#### Federal Summary

| Label | Value |
|---|---|
| Ordinary Tax | `$X,XXX` |
| Preferential Tax | `$X,XXX` |
| **Total Federal Tax** | `$X,XXX` |
| Effective Rate | `X.XX%` |
| Marginal Bracket Rate | `XX%` |

---

### Section: Ohio Tax

Only shown when `include_ohio = true` and `ohio.included = true` in response.

#### Ohio Calculation Detail

Displayed as a vertical list mirroring the Ohio calculation flow:

| Label | Value |
|---|---|
| Ohio AGI | `$XX,XXX` |
| Personal Exemption | `($X,XXX)` |
| Medical Deduction | `($X,XXX)` (hidden if zero) |
| **Ohio Tax Base** | `$XX,XXX` |
| Tax Before Credits | `$XXX` |
| Retirement Income Credit | `($XXX)` (hidden if zero) |
| **Ohio Tax** | `$XXX` |
| Effective Rate | `X.XX%` |

---

### Section: Summary

Always shown at the bottom of the output panel.

| Label | Value |
|---|---|
| Total Federal Tax | `$X,XXX` |
| Total Ohio Tax | `$XXX` (shown only if include_ohio = true) |
| **Grand Total Tax** | `$X,XXX` |
| **Overall Effective Rate** | `X.XX%` |

---

## Error Handling

- HTTP 422: display `detail` field in red below the inputs panel
- HTTP 500: display generic error message in red
- Network error: display "Could not reach the server. Is the API running?" in red
- Clear previous error on each new calculation

---

## Number Formatting

- Dollar amounts: `$XX,XXX` with comma separators, no decimal places
- Negative amounts (deductions): shown in parentheses `($X,XXX)` in gray
- Rates: `X.XX%` with two decimal places
- Zero dollar amounts: shown as `$0`
- Zero rates: shown as `0.00%`

---

## On Page Load

1. Call `GET /api/tax-years` — populate tax year dropdown, set default
2. Call `GET /api/config` — load any relevant config defaults
3. Fire initial calculation with all-zero inputs — displays zero-tax baseline

---

## External Dependencies

No Plotly needed — this page is tables and text only.
No external dependencies. All styling inline or in a `<style>` block.

---

## Styling

Consistent with `index.html` and `income.html`.
- Background: `#f8f9fa`, white cards
- Font: system font stack
- Bracket tables: clean, minimal borders, alternating row backgrounds
- Marginal bracket row: subtle highlight (e.g. light blue background)
- Bold labels for key subtotals (AGI, Taxable Income, Total Tax)
- Deduction amounts in gray with parentheses
- Loading state: output panel at 50% opacity while request in flight

---

## Out of Scope

- Sweep chart (use EMR Analysis page)
- ACA subsidy interaction
- IRMAA
- AMT
- Tax credits
- Print / export
- Multi-year projection
