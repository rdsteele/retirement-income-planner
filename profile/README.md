# Personal Profile Data

This directory contains your personal financial data. It is excluded from
version control. Create your own `accounts.json` here based on the example
below.

---

## Getting Started

Copy the example below into `profile/accounts.json` and edit it with your
actual account balances and holdings. The file is read by the accounts API
on startup; if it does not exist, an empty list is assumed.

---

## accounts.json Example

```json
[
  {
    "id": "taxable-brokerage",
    "name": "Taxable Brokerage",
    "account_type": "taxable",
    "balance": null,
    "annual_contribution": null,
    "holdings": [
      {
        "id": "vti-holding",
        "ticker": "VTI",
        "basis": 45000.00,
        "value": 80000.00,
        "unrealized_gain": 35000.00
      }
    ],
    "total_basis": 45000.00,
    "total_value": 80000.00,
    "total_unrealized_gain": 35000.00
  },
  {
    "id": "trad-ira",
    "name": "Traditional IRA",
    "account_type": "traditional",
    "balance": 320000.00,
    "annual_contribution": null,
    "holdings": null,
    "total_basis": null,
    "total_value": null,
    "total_unrealized_gain": null
  },
  {
    "id": "roth-ira",
    "name": "Roth IRA",
    "account_type": "roth",
    "balance": 95000.00,
    "annual_contribution": null,
    "holdings": null,
    "total_basis": null,
    "total_value": null,
    "total_unrealized_gain": null
  },
  {
    "id": "hsa",
    "name": "HSA",
    "account_type": "hsa",
    "balance": 28000.00,
    "annual_contribution": 4300.00,
    "holdings": null,
    "total_basis": null,
    "total_value": null,
    "total_unrealized_gain": null
  }
]
```

---

## Account Types

| `account_type` | Description |
|---|---|
| `taxable` | Brokerage account — tracks per-holding basis and unrealized gain |
| `traditional` | Traditional IRA / 401k — balance only, withdrawals are ordinary income |
| `roth` | Roth IRA / Roth 401k — balance only, withdrawals are MAGI-neutral |
| `hsa` | Health Savings Account — balance and annual contribution |

Taxable accounts require a `holdings` list. All other account types use a
`balance` field and leave `holdings` as `null`.
