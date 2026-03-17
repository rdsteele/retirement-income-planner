# Spec: Account Management Page

**Version:** 1.0
**Status:** Draft
**Covers:** `api/static/accounts.html`, nav bar updates on all pages

---

## Purpose

Manage the account inventory stored in `profile/accounts.json`. Provides
a UI for all CRUD operations on accounts and holdings, plus bulk update
via CSV paste. Replaces the need to use curl commands or direct JSON editing.

---

## Serving

Accessible at `/static/accounts.html`.

---

## Navigation Bar

Add "Accounts" as the fifth nav item on all pages:

```
Income Planning | EMR Analysis | Tax Detail | Scenarios | Accounts
```

Update nav bar in `index.html`, `tax.html`, `income.html`, `scenarios.html`,
and `accounts.html`.

---

## Layout

Single column, max-width 960px, centered. Same styling as `scenarios.html`.

---

## Sections

### Portfolio Summary

Read-only summary card at the top, loaded from `GET /api/accounts/summary`
on page load and refreshed after any change.

| Field | Value |
|---|---|
| Taxable Value | $XXX,XXX |
| Taxable Basis | $XXX,XXX |
| Taxable Unrealized Gain | $XXX,XXX |
| Tax-Deferred Balance | $XXX,XXX |
| Roth Balance | $XXX,XXX |
| HSA Balance | $XXX,XXX |
| HSA Annual Contribution | $X,XXX |
| Total Portfolio | $XXX,XXX |

---

### Accounts List

Loaded from `GET /api/accounts` on page load.
Accounts displayed in this order: taxable, traditional, roth, hsa.
Within each type, alphabetical by name.

#### Non-taxable accounts (traditional, roth, hsa)

Displayed as a compact row:

```
[ Account Name ]  [ Type badge ]  Balance: $XXX,XXX  [Edit] [Delete]
```

For HSA accounts, also show Annual Contribution: $X,XXX.

**Edit** — opens inline edit form within the row:
- Account name (text input)
- Balance (number input)
- Annual contribution (number input, HSA only)
- [Save] [Cancel] buttons
- On Save: `PUT /api/accounts/{id}`, refresh row

**Delete** — immediately calls `DELETE /api/accounts/{id}`, removes row,
refreshes portfolio summary.

#### Taxable accounts

Displayed as an expandable card (expanded by default):

```
▼ [ Account Name ]  [ taxable badge ]
  Total: Value $XXX,XXX | Basis $XXX,XXX | Gain $XXX,XXX  [Edit Name] [Delete Account] [Add Holding]
  
  Table: Holding | Value | Basis | Unrealized Gain | Actions
  ─────────────────────────────────────────────────────────
  FXAIX   $63,098   $20,350   $42,748   [Edit] [Delete]
  FSKAX   $83,514   $40,596   $42,918   [Edit] [Delete]
```

**Edit Name** — inline edit of account name only.

**Delete Account** — immediately deletes account and all holdings,
refreshes list.

**Add Holding** — reveals inline form at bottom of holdings table:
- Ticker (text input, auto-uppercased)
- Value (number input)
- Basis (number input)
- [Add] [Cancel] buttons
- On Add: `POST /api/accounts/{id}/holdings`, refresh card

**Edit holding** — opens inline edit form within the holding row:
- Ticker, Value, Basis inputs
- [Save] [Cancel]
- On Save: `PUT /api/accounts/{id}/holdings/{hid}`, refresh card

**Delete holding** — immediately calls
`DELETE /api/accounts/{id}/holdings/{hid}`, removes row, refreshes
account totals and portfolio summary.

---

### Add Account

Form below the accounts list:

| Field | Input | Notes |
|---|---|---|
| Account Name | text | Required |
| Account Type | select | taxable, traditional, roth, hsa |
| Balance | number | traditional, roth, hsa only — hidden for taxable |
| Annual Contribution | number | hsa only |

[Add Account] button — `POST /api/accounts`, refreshes accounts list
and portfolio summary.

Account type selection shows/hides Balance and Annual Contribution fields.

---

### Bulk Update (CSV)

Textarea for pasting CSV data. Format:

```
account,type,holding,value,basis
Fidelity Brokerage,taxable,FXAIX,63098.39,20350
Fidelity Brokerage,taxable,FSKAX,83514.36,40596
Fidelity Brokerage,taxable,FCASH,112.04,0
Fidelity Brokerage,taxable,VUSXX,18375.66,3938
Vanguard Brokerage,taxable,PRIMECAP,50000,37000
Vanguard Brokerage,taxable,PRIMECAP,23000,6000
Treasury Direct,taxable,IBOND,45000,40000
Synchrony Bank,taxable,HYSA,1000,1000
Rollover IRA,traditional,,1000000,
Roth IRA,roth,,900000,
HSA,hsa,,100000,5400
```

**Column definitions:**
- `account` — account name, must match existing account name + type exactly
  OR creates a new account if not found
- `type` — account type: `taxable`, `traditional`, `roth`, `hsa`
- `holding` — ticker symbol (taxable only; ignored for non-taxable)
- `value` — current market value
- `basis` — cost basis (taxable holdings only; for HSA used as
  `annual_contribution`; ignored for traditional/roth)

**Processing rules:**
- Match on `account` + `type` combination (exact, case-insensitive)
- If match found (taxable): replace ALL existing holdings with rows
  from CSV for that account
- If match found (non-taxable): update balance (and annual_contribution
  for HSA)
- If no match: create new account with provided data
- Header row required — first row must be `account,type,holding,value,basis`
- Empty `holding` or `basis` cells are treated as blank/zero
- Errors shown per row — processing continues on other rows

**UI:**
- Textarea (10 rows) with placeholder showing example CSV
- [Preview] button — parses CSV and shows a preview table of changes
  before applying:
  - "Will update: Fidelity Brokerage (replace 4 holdings)"
  - "Will create: New Account (taxable, 2 holdings)"
- [Apply] button — executes the updates via API calls
- Results summary shown after apply: "Updated 3 accounts, created 1 account,
  0 errors"
- Error messages shown inline for any failed rows

---

## API calls used

All existing endpoints from `api/routers/accounts.py` — no new backend
needed:

- `GET /api/accounts` — load accounts list
- `GET /api/accounts/summary` — load portfolio summary
- `POST /api/accounts` — create account
- `PUT /api/accounts/{id}` — update account
- `DELETE /api/accounts/{id}` — delete account
- `POST /api/accounts/{id}/holdings` — add holding
- `PUT /api/accounts/{id}/holdings/{hid}` — update holding
- `DELETE /api/accounts/{id}/holdings/{hid}` — delete holding

---

## Styling

Consistent with `scenarios.html` and other pages.
- Type badges: small colored pills
  - taxable: blue
  - traditional: orange
  - roth: green
  - hsa: teal
- Inline edit forms: subtle background highlight on the row being edited
- Bulk update textarea: monospace font
- Preview table: same style as accounts list but read-only

---

## No new backend needed

All API endpoints already exist. This is a pure frontend addition.

---

## Out of Scope

- Import/export accounts as JSON (use profile/accounts.json directly)
- Account transaction history
- Performance tracking
- Automatic balance refresh from brokerage APIs
- Multi-currency support
