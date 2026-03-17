# Spec: Scenarios

**Version:** 1.0
**Status:** Draft
**Covers:** `services/scenarios.py`, `api/routers/scenarios.py`, `api/models/scenarios.py`, `api/static/scenarios.html`, nav bar updates on all pages

---

## Purpose

Save, load, export, and import named planning scenarios. A scenario is a
snapshot of all input fields across all pages — income planning, EMR analysis,
and tax detail. Account balances are not stored in scenarios — they live in
`profile/accounts.json` and are shared across all scenarios.

Scenarios enable:
- Saving a planning baseline ("2026 Base Plan")
- Creating variations ("2026 Heavy Conversion", "2026 Conservative")
- Resuming work across browser sessions
- Sharing plans with others via JSON export/import

---

## Storage

### Scenario files
`profile/scenarios/{name}.json` — one file per scenario.
Filename is the scenario name with spaces replaced by underscores and
special characters removed. Example: "2026 Base Plan" → `2026_Base_Plan.json`.

### Current scenario tracking
`profile/current_scenario.json` — single file tracking which scenario
is currently loaded:
```json
{ "name": "2026 Base Plan" }
```
Empty or missing = no scenario loaded.

Both locations are excluded from git via `.gitignore` entry `profile/scenarios/`
(already present) and `profile/current_scenario.json` (add if not present).

---

## Scenario File Schema

```json
{
  "name": "2026 Base Plan",
  "saved_at": "2026-03-16T19:00:00",
  "version": "1.0",
  "inputs": {
    "tax_year": 2026,
    "filing_status": "single",
    "pension": 1596,
    "interest": 3250,
    "ordinary_dividends": 0,
    "qualified_dividends": 0,
    "ira_distributions": 2675,
    "ss_benefit": 0,
    "fixed_ltcg": 11875,
    "tax_exempt_interest": 0,
    "above_the_line_adjustments": 5400,
    "additional_deductions": 0,
    "wages": 0
  },
  "ohio": {
    "include_ohio": true,
    "gross_medical_expenses": 0,
    "ohio_qualifying_retirement_income": 0,
    "ohio_us_obligation_interest": 0
  },
  "aca": {
    "include_aca": true
  },
  "emr_settings": {
    "sweep_mode": "ordinary",
    "sweep_floor": 0,
    "sweep_ceiling": null,
    "sweep_step": 100,
    "variable_ordinary": 0,
    "irmaa_adjust": false,
    "irmaa_inflation_rate": 2.5
  },
  "income_planning": {
    "essential_spending": 60000,
    "discretionary_spending": 40000,
    "withdrawals": [
      {
        "holding_id": "uuid",
        "withdraw": 10000,
        "basis_portion": 10000,
        "basis_manual_override": false
      }
    ],
    "trad_withdrawals": [
      { "account_id": "uuid", "amount": 13500 }
    ],
    "roth_withdrawals": [
      { "account_id": "uuid", "amount": 0 }
    ],
    "hsa_withdrawals": [
      { "account_id": "uuid", "amount": 0 }
    ]
  }
}
```

### Field ownership

| Section | Fields | Used by pages |
|---|---|---|
| `inputs` | All income fields, tax year, filing status | All three pages |
| `ohio` | Ohio settings | All three pages |
| `aca` | ACA toggle | EMR, Income Planning |
| `emr_settings` | Sweep controls, IRMAA | EMR page only |
| `income_planning` | Spending, withdrawal mix | Income Planning only |
```

### Notes
- All monetary values stored as numbers (no Decimal — JSON boundary)
- `version` field for future migration support
- Withdrawal entries reference account/holding IDs from `profile/accounts.json`
  — if an ID no longer exists when loading, that withdrawal entry is silently
  skipped and the field left at zero
- `saved_at` is ISO 8601 UTC timestamp

---

## Service Interface

```python
# services/scenarios.py

from dataclasses import dataclass
from datetime import datetime

@dataclass
class ScenarioMeta:
    name: str
    saved_at: datetime
    filename: str

def list_scenarios() -> list[ScenarioMeta]: ...
def load_scenario(name: str) -> dict: ...          # returns raw JSON dict
def save_scenario(name: str, data: dict) -> None: ...
def delete_scenario(name: str) -> None: ...
def get_current_scenario() -> str | None: ...      # returns name or None
def set_current_scenario(name: str | None) -> None: ...
def scenario_name_to_filename(name: str) -> str: ...  # "2026 Base Plan" → "2026_Base_Plan.json"
```

Error behavior:
- `load_scenario` raises `ValueError` if scenario not found
- `delete_scenario` raises `ValueError` if scenario not found
- `save_scenario` overwrites if name exists (caller is responsible for
  confirming overwrite)
- `list_scenarios` returns empty list if `profile/scenarios/` does not exist

---

## API Endpoints

Registered in `api/main.py`. All under `/api/scenarios`.

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/api/scenarios` | List all scenarios | 200 |
| `GET` | `/api/scenarios/current` | Get current scenario name | 200 |
| `POST` | `/api/scenarios/current` | Set current scenario name | 200 |
| `GET` | `/api/scenarios/{name}` | Load scenario by name | 200 |
| `POST` | `/api/scenarios/{name}` | Save scenario | 200 |
| `DELETE` | `/api/scenarios/{name}` | Delete scenario | 204 |

**Router registration:** `/api/scenarios/current` must be registered before
`/api/scenarios/{name}` to prevent FastAPI routing "current" as a name.

### Response shapes

`GET /api/scenarios` returns:
```json
[
  { "name": "2026 Base Plan", "saved_at": "2026-03-16T19:00:00" },
  { "name": "2026 Heavy Conversion", "saved_at": "2026-03-15T10:30:00" }
]
```

`GET /api/scenarios/current` returns:
```json
{ "name": "2026 Base Plan" }
```
or `{ "name": null }` if none loaded.

`GET /api/scenarios/{name}` returns the full scenario JSON dict.

`POST /api/scenarios/{name}` request body is the full scenario JSON dict.

---

## Scenarios Page (`api/static/scenarios.html`)

Accessible at `/static/scenarios.html`. Added to nav bar on all pages.

### Layout

Single column, centered, max-width 800px.

### Sections

**Current Scenario**
- Shows currently loaded scenario name or "None"
- "Clear" button to unload current scenario

**Saved Scenarios**
Table with columns: Name | Saved | Actions

Actions per row:
- **Load** — loads scenario, sets as current, navigates to income planning page
- **Export** — downloads scenario JSON file to browser
- **Delete** — confirms then deletes

Empty state: "No saved scenarios. Use Save or Save As on any page to create one."

**Import**
- File picker accepting `.json` files
- On file selection: reads JSON, validates structure, saves as scenario
- Shows success or error message
- If name conflicts, prompts to overwrite or rename

**New Scenario**
- Text input for scenario name
- "Create" button — creates empty scenario with current date, sets as current,
  navigates to income planning page

---

## Nav Bar Updates (all pages)

Updated nav bar on `index.html`, `tax.html`, `income.html`, `scenarios.html`:

```
[ Retirement Income Planner ]   
Income Planning | EMR Analysis | Tax Detail | Scenarios
📋 2026 Base Plan  [Save] [Save As]
```

- Scenario name shown below nav links, left-aligned
- **Save** button — saves current page inputs to loaded scenario
  (disabled if no scenario loaded)
- **Save As** button — prompts for new name, saves, sets as current
- If no scenario loaded: shows "📋 No scenario loaded"
- Clicking scenario name navigates to scenarios page

### Save behavior

All pages save to the same shared `inputs`, `ohio`, and `aca` sections.
Page-specific sections are only updated by the page that owns them.

**All pages save:** `inputs`, `ohio`, `aca`

**EMR page additionally saves:** `emr_settings`

**Income Planning page additionally saves:** `income_planning`

**Tax Detail page:** no page-specific section — uses shared inputs only.

Save reads current field values from the page and writes to the scenario
file. Other sections in the scenario are preserved.

### Load behavior

When a scenario is loaded (from scenarios page or on page load if
current scenario is set):
- All input fields on the current page are populated from the
  scenario's section for that page
- Fields not present in the scenario are left at their defaults
- Withdrawal mix entries reference account IDs — missing IDs are skipped
- Page recalculates after load (fires Calculate/Run Analysis)

### Page load behavior

On every page load:
1. `GET /api/scenarios/current` — get current scenario name
2. If name exists: `GET /api/scenarios/{name}` — load scenario data
3. Populate fields for this page's section
4. Show scenario name in nav bar
5. Fire initial calculation

---

## Export / Import

**Export:**
- `GET /api/scenarios/{name}` returns JSON
- Frontend triggers browser download: `scenario_name.json`
- No special endpoint needed — standard fetch + blob download

**Import:**
- User selects `.json` file via file picker
- Frontend reads file as text, parses JSON
- Validates: must have `name`, `version`, at least one of
  `income_planning`, `emr`, `tax_detail`
- `POST /api/scenarios/{name}` with parsed JSON
- On success: sets as current, shows confirmation

---

## Tests

`tests/unit/test_scenarios.py`:
1. `list_scenarios` returns empty list when directory missing
2. `save_scenario` creates file, `load_scenario` returns same data
3. `delete_scenario` removes file
4. `delete_scenario` raises ValueError for missing scenario
5. `scenario_name_to_filename` handles spaces and special characters
6. `get_current_scenario` returns None when file missing
7. `set_current_scenario` persists name, `get_current_scenario` returns it
8. `set_current_scenario(None)` clears current scenario

`tests/functional/test_scenarios_route.py`:
1. `GET /api/scenarios` returns empty list
2. `POST /api/scenarios/{name}` saves, `GET /api/scenarios/{name}` returns same
3. `DELETE /api/scenarios/{name}` returns 204
4. `DELETE /api/scenarios/{name}` returns 404 for missing
5. `GET /api/scenarios/current` returns null when none set
6. `POST /api/scenarios/current` sets name, `GET` returns it
7. `/api/scenarios/current` registered before `/{name}` (no routing conflict)

---

## .gitignore additions

```
profile/current_scenario.json
```

(`profile/scenarios/` already present from earlier.)

---

## Out of Scope

- Scenario comparison (side by side)
- Scenario versioning / history
- Scenario notes / annotations
- Multi-user scenarios
- Cloud sync
- Scenario templates
