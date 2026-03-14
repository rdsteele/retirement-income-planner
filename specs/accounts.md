# Spec: Account Inventory Service

**Version:** 1.0
**Status:** Draft
**Covers:** `services/accounts.py`, `api/routers/accounts.py`, `api/models/accounts.py`

---

## Purpose

Store and retrieve a personal account inventory — taxable brokerage, tax-deferred
(traditional IRA / 401k), Roth (Roth IRA / Roth 401k), and HSA accounts. Provides
the account data consumed by the income planning page for withdrawal mix inputs and
portfolio summary display.

---

## Architecture Rules

- Service layer owns all business logic and file I/O
- Route is a thin wrapper — deserialize, call service, serialize, handle errors
- `Decimal` is used inside the service; route converts to `float` at the API boundary
- Derived values (unrealized gain, account totals, portfolio summary) are computed on
  read and never stored
- File path is injectable via a `_path` parameter on service functions for test isolation

---

## Data Storage

### File Location

`data/accounts.json` — single JSON file, list of account objects.
Initialized as `[]` if the file does not exist.

### Account Types

| `account_type` | Description |
|---|---|
| `"taxable"` | Taxable brokerage — holds a list of holdings |
| `"traditional"` | Traditional IRA or 401k — single balance |
| `"roth"` | Roth IRA or Roth 401k — single balance |
| `"hsa"` | Health Savings Account — balance plus annual contribution |

### Stored Schema

```json
[
  {
    "id": "uuid4-string",
    "name": "Fidelity Taxable",
    "account_type": "taxable",
    "holdings": [
      { "id": "uuid4-string", "ticker": "VTI",  "basis": 45000.00, "value": 82000.00 },
      { "id": "uuid4-string", "ticker": "VTI",  "basis": 12000.00, "value": 18000.00 },
      { "id": "uuid4-string", "ticker": "VXUS", "basis":  8000.00, "value": 11000.00 }
    ]
  },
  {
    "id": "uuid4-string",
    "name": "Fidelity Traditional IRA",
    "account_type": "traditional",
    "balance": 320000.00
  },
  {
    "id": "uuid4-string",
    "name": "Fidelity Roth IRA",
    "account_type": "roth",
    "balance": 95000.00
  },
  {
    "id": "uuid4-string",
    "name": "Fidelity HSA",
    "account_type": "hsa",
    "balance": 28000.00,
    "annual_contribution": 5400.00
  }
]
```

Fields `holdings`, `balance`, and `annual_contribution` are mutually exclusive
by `account_type`. `holdings` is only present for `"taxable"`. `annual_contribution`
is only present for `"hsa"`. `balance` is present for `"traditional"`, `"roth"`,
and `"hsa"`.

Numbers are stored as JSON floats. The service converts to `Decimal` on load
and back to `float` on save.

---

## Dataclasses

### HoldingIn

Input shape for creating or updating a holding. `ticker` is normalized to uppercase.

| Field | Type | Notes |
|---|---|---|
| `ticker` | `str` | Normalized to uppercase on write |
| `basis` | `Decimal` | Total cost basis, non-negative |
| `value` | `Decimal` | Current market value, non-negative |

### HoldingOut

Returned shape for a holding, includes derived field.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | uuid4 |
| `ticker` | `str` | Uppercase |
| `basis` | `Decimal` | |
| `value` | `Decimal` | |
| `unrealized_gain` | `Decimal` | Derived: `value - basis` |

### AccountIn

Input shape for creating or updating an account.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Display name |
| `account_type` | `str` | One of `"taxable"`, `"traditional"`, `"roth"`, `"hsa"` |
| `balance` | `Decimal \| None` | Required for `traditional`, `roth`, `hsa` |
| `annual_contribution` | `Decimal \| None` | Optional, `hsa` only |
| `holdings` | `list[HoldingIn] \| None` | Required for `taxable` |

### AccountOut

Returned shape for an account, includes derived totals for taxable accounts.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | uuid4 |
| `name` | `str` | |
| `account_type` | `str` | |
| `balance` | `Decimal \| None` | |
| `annual_contribution` | `Decimal \| None` | |
| `holdings` | `list[HoldingOut] \| None` | With derived `unrealized_gain` per holding |
| `total_value` | `Decimal \| None` | Taxable only: sum of holding values |
| `total_basis` | `Decimal \| None` | Taxable only: sum of holding bases |
| `total_unrealized_gain` | `Decimal \| None` | Taxable only: `total_value - total_basis` |

### PortfolioSummary

| Field | Type | Notes |
|---|---|---|
| `taxable_value` | `Decimal` | Sum of all taxable account holding values |
| `taxable_basis` | `Decimal` | Sum of all taxable account holding bases |
| `taxable_unrealized_gain` | `Decimal` | `taxable_value - taxable_basis` |
| `traditional_balance` | `Decimal` | Sum of all traditional account balances |
| `roth_balance` | `Decimal` | Sum of all Roth account balances |
| `hsa_balance` | `Decimal` | Sum of all HSA account balances |
| `hsa_annual_contribution` | `Decimal` | Sum of HSA `annual_contribution` fields |
| `total_portfolio_value` | `Decimal` | Sum of all account values across all types |

---

## Service Interface

```python
# services/accounts.py

def load_accounts(_path: Path = _DATA_PATH) -> list[AccountOut]: ...
def get_account(account_id: str, _path: Path = _DATA_PATH) -> AccountOut: ...
def create_account(data: AccountIn, _path: Path = _DATA_PATH) -> AccountOut: ...
def update_account(account_id: str, data: AccountIn, _path: Path = _DATA_PATH) -> AccountOut: ...
def delete_account(account_id: str, _path: Path = _DATA_PATH) -> None: ...

def create_holding(account_id: str, data: HoldingIn, _path: Path = _DATA_PATH) -> AccountOut: ...
def update_holding(account_id: str, holding_id: str, data: HoldingIn, _path: Path = _DATA_PATH) -> AccountOut: ...
def delete_holding(account_id: str, holding_id: str, _path: Path = _DATA_PATH) -> AccountOut: ...

def get_portfolio_summary(_path: Path = _DATA_PATH) -> PortfolioSummary: ...
```

### Error Behavior

- `get_account`, `update_account`, `delete_account`: raise `ValueError` if `account_id` not found
- `create_holding`, `update_holding`, `delete_holding`: raise `ValueError` if `account_id`
  or `holding_id` not found
- Holding operations on non-taxable accounts: raise `ValueError`
- Holding and balance operations return the updated `AccountOut` immediately after write

---

## Derived Value Rules

### Per Holding
```
unrealized_gain = value - basis
```

### Per Taxable Account
```
total_value          = sum(h.value for h in holdings)
total_basis          = sum(h.basis for h in holdings)
total_unrealized_gain = total_value - total_basis
```

### Portfolio Summary
```
taxable_value          = sum(account.total_value for taxable accounts)
taxable_basis          = sum(account.total_basis for taxable accounts)
taxable_unrealized_gain = taxable_value - taxable_basis
traditional_balance    = sum(account.balance for traditional accounts)
roth_balance           = sum(account.balance for roth accounts)
hsa_balance            = sum(account.balance for hsa accounts)
hsa_annual_contribution = sum(account.annual_contribution or 0 for hsa accounts)
total_portfolio_value  = taxable_value + traditional_balance + roth_balance + hsa_balance
```

---

## API Endpoints

Registered in `api/main.py`. All under `/api/accounts`.

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/api/accounts` | List all accounts with derived fields | 200 |
| `POST` | `/api/accounts` | Create account | 201 |
| `GET` | `/api/accounts/summary` | Portfolio summary aggregates | 200 |
| `GET` | `/api/accounts/{id}` | Get single account | 200 |
| `PUT` | `/api/accounts/{id}` | Update account | 200 |
| `DELETE` | `/api/accounts/{id}` | Delete account | 204 |
| `POST` | `/api/accounts/{id}/holdings` | Add holding to taxable account | 201 |
| `PUT` | `/api/accounts/{id}/holdings/{hid}` | Update holding | 200 |
| `DELETE` | `/api/accounts/{id}/holdings/{hid}` | Delete holding | 200 (returns updated account) |

**Router registration order:** `/api/accounts/summary` must be registered before
`/api/accounts/{id}` to prevent FastAPI from routing the literal string `"summary"`
as an account ID.

### Request / Response Models

Pydantic models in `api/models/accounts.py` mirror the service dataclasses with
`float` fields in place of `Decimal`. Route converts `float` → `Decimal` on input
using `Decimal(str(value))` and `Decimal` → `float` on output.

### Error Responses

- `422` — Pydantic validation error (invalid request shape)
- `404` — Account or holding not found (`ValueError` from service)
- `500` — Unexpected error

---

## Multiple Entries Per Ticker

A taxable account may hold multiple entries for the same ticker. This is intentional
— different purchase tranches have different cost bases. Each entry has its own `id`
and is managed independently. The service does not merge or aggregate by ticker.

Example: two VTI entries with different bases represent shares purchased at different
times or prices. The income planning page displays them separately so the user can
choose which holding to withdraw from.

---

## Tests

`tests/unit/test_accounts.py` — uses `tmp_path` fixture, no real file access:

1. `load_accounts` returns empty list when file does not exist
2. Create account — all four types
3. Get account by id — returns correct account
4. Get account by id — raises `ValueError` for missing id
5. Update account — fields updated, id preserved
6. Delete account — account removed from list
7. `unrealized_gain` derived correctly per holding
8. Derived totals correct per taxable account (`total_value`, `total_basis`, `total_unrealized_gain`)
9. Multiple holdings for same ticker handled independently
10. Create holding — adds to correct account, returns updated `AccountOut`
11. Update holding — updates fields, id preserved
12. Delete holding — removes from account, returns updated `AccountOut`
13. Holding operations on non-taxable account raise `ValueError`
14. Portfolio summary aggregates correctly across all account types
15. HSA `annual_contribution` stored, returned, and included in summary
16. `hsa_annual_contribution = 0` in summary when no HSA accounts present

---

## Out of Scope

- Authentication
- Multi-user accounts
- Per-lot tax tracking (purchase date, shares, cost per share)
- Automatic balance refresh from brokerage APIs
- Asset allocation analysis
- Save / load from file (manual backup — deferred to future phase)
