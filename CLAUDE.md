# Retirement Income Planning — Project Context

## Purpose
A locally-run personal tool for retirement income and tax planning. Supports federal and state
tax calculations, Social Security taxability analysis, marginal effective tax rate (MER)
calculations, and multi-stream annual income planning.

---

## Architecture — Non-Negotiable Rules

This project enforces strict layer separation:

- **Data layer** (`data/`) — tax bracket definitions (JSON by year), saved user scenarios. No logic.
- **Service layer** (`services/`) — all tax and planning logic. Pure Python, zero knowledge of the
  API or UI layer. Services can be imported and used independently or composed together.
- **API layer** (`api/`) — FastAPI routes. Thin wrappers that call service functions and return
  results. No tax logic belongs here.
- **UI layer** (`api/templates/`, `api/static/`) — frontend. TBD between HTMX and Vue.js.
  Will be built after APIs are complete.

**The cardinal rule: services never import from `api/`. API routes import from `services/`.
Never the reverse.**

---

## Service Composability

Services are designed to work both independently and composed:

- `social_security`, `federal_tax` and `state_tax` are standalone — usable directly via API or in tests
- `marginal_rate` composes `social_security` `federal_tax` and `state_tax`
- `income_planner` composes all services for full scenario analysis

When adding a new service, ask: can this be used standalone? If yes, ensure it has its own
router in `api/routers/` and its own independent tests.

---

## Data Conventions

- **Always use `Decimal` for all monetary amounts and rates. Never `float`.** Floating point
  errors are unacceptable in tax calculations.
- **Always round tax amounts using `ROUND_HALF_UP`. Never use Python's built-in `round()`.**
  Use a shared `round_tax()` helper in `services/common.py`.
- Tax bracket data lives in `data/brackets/federal_{year}.json` and `data/brackets/{state}_{year}.json`.
  Adding a new tax year means adding a new file — never modify existing year files.
- Saved user scenarios are stored as JSON in `data/scenarios/`.

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

**No test ever starts a live server or writes to `data/scenarios/`.**
