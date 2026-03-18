# Retirement Income Planning — Project Context

## Purpose
A locally-run personal tool for retirement income and tax planning. Supports federal and Ohio
state tax calculations, Social Security taxability analysis, effective marginal rate (EMR)
calculations, ACA subsidy modeling, and multi-stream annual income planning.

---

## Architecture — Non-Negotiable Rules

This project enforces strict layer separation:

- **Data layer** (`data/`) — tax bracket definitions (JSON by year), ACA schedule data. No logic.
- **Service layer** (`services/`) — all tax and planning logic. Pure Python, zero knowledge of the
  API or UI layer. Services can be imported and used independently or composed together.
- **API layer** (`api/`) — FastAPI routes. Thin wrappers that call service functions and return
  results. No tax logic belongs here.
- **UI layer** (`api/static/`) — vanilla JS and HTML. No frameworks. Plotly served locally.

**The cardinal rule: services never import from `api/`. API routes import from `services/`.
Never the reverse.**

---

## Service Composability

Services are designed to work both independently and composed:

- `federal_tax`, `ohio_tax`, `social_security` are standalone — usable directly via API or in tests
- `emr` composes `federal_tax`, `ohio_tax`, and `social_security`
- `total_cost` composes `emr` and `aca` for full tax + ACA subsidy EMR
- `accounts` and `scenarios` are standalone CRUD services over profile JSON files
- `data_loader` is a shared utility for loading bracket and threshold data

When adding a new service, ask: can this be used standalone? If yes, ensure it has its own
router in `api/routers/` and its own independent tests.

---

## Services

| Service | Description |
|---|---|
| `federal_tax` | 2025/2026 federal brackets, ordinary + preferential income stacking |
| `ohio_tax` | 2025/2026 Ohio tax, tiered exemption, medical deduction, retirement credit |
| `social_security` | SS taxability, provisional income, torpedo calculation |
| `emr` | Effective marginal rate sweep, all components, boundary point insertion |
| `aca` | ACA subsidy from schedule-based interpolation, cliff detection |
| `total_cost` | Combines tax EMR + ACA subsidy loss into total cost EMR |
| `accounts` | Account inventory CRUD (taxable/traditional/roth/hsa) |
| `scenarios` | Save/load/export/import named planning scenarios |
| `data_loader` | Shared bracket and threshold data loading |

---

## Pages

| Page | File | Description |
|---|---|---|
| Income Planning | `income.html` | Main planning page, Tax Map visualization |
| EMR Analysis | `emr.html` | Detailed EMR sweep chart |
| Tax Detail | `tax.html` | Point-in-time federal + Ohio tax breakdown |
| Scenarios | `scenarios.html` | Scenario admin — save/load/export/import |
| Accounts | `accounts.html` | Account inventory management |

Default route `/` redirects to `income.html`. `/emr` redirects to `emr.html`.

---

## Data Conventions

- **Always use `Decimal` for all monetary amounts and rates. Never `float`.** Floating point
  errors are unacceptable in tax calculations.
- **Always round tax amounts using `ROUND_HALF_UP`. Never use Python's built-in `round()`.**
  Use the shared `round_tax()` helper in `services/common.py`.
- Tax bracket data lives in `data/brackets/federal_{year}.json` and `data/brackets/ohio_{year}.json`.
  Adding a new tax year means adding a new file — never modify existing year files.
- ACA schedule data lives in `data/aca/aca_{year}.json`. Updated annually by the user.
- User scenarios are stored as JSON in `profile/scenarios/` (gitignored).
- Account data is stored in `profile/accounts.json` (gitignored).

---

## Hardcoding Rules — Non-Negotiable

**Never hardcode values that come from configuration or data files.**
This includes but is not limited to:
- Tax years (e.g. `2025`, `2026`)
- Filing statuses (e.g. `"single"`, `"mfj"`)
- Dollar thresholds, bracket boundaries, or rates
- Page URLs or route paths

These values must always be:
- **Backend:** loaded from data files in `data/` via `data_loader.py`
- **Frontend:** populated dynamically from an `APP_CONFIG` object or
  from an API response — never written inline in HTML or as JS constants

**The only acceptable hardcoded values** are structural constants that
will never change regardless of tax law or configuration — for example,
the NIIT rate (3.8%) is statutory and has not changed since 2013, but
even then prefer loading from data if it already exists there.

If you find yourself writing a literal year, dollar amount, or filing
status string anywhere outside of a data file or test fixture, stop and
ask whether it should come from config instead.

---

## Coding Style

- **Prefer small, single-purpose functions.** If a function is doing more than one
  logical thing, break it into smaller functions. Each function should be
  describable in one sentence.
- Functions that calculate, functions that load data, and functions that orchestrate
  others should be kept separate.

---

## Testing Philosophy

Three distinct tiers — each lives in a separate directory:

- **`tests/unit/`** — one module at a time, mocked dependencies, no file I/O, no server.
  Tests service logic in complete isolation.
- **`tests/functional/`** — full stack via FastAPI `TestClient`, real bracket data files,
  no mocks. Exercises routing, serialization, and service composition together.
- **`tests/scenarios/`** — named real-world tax scenarios with fully hand-verified expected
  outputs. These are regression anchors — if they break, something fundamental changed.
  Example: `test_scenario_ss_torpedo_single_filer.py`

**No test ever starts a live server or writes to `profile/`.**
