# Session Starter

Copy and paste the appropriate section below at the start of a new Claude session.
Upload the relevant spec files listed for each session type.

---

## Design Session (developing a new spec)

```
I'm working on a Python/FastAPI retirement income planning application.

GitHub: https://github.com/rdsteele/retirement-income-planner
Tech stack: FastAPI, vanilla JS, Plotly, local JSON file storage, Python 3.12+

## Application Overview

A local retirement income planning tool for federal/state tax analysis,
ACA subsidy planning, and annual withdrawal planning. Runs entirely on
localhost — no cloud, no authentication.

## Pages
- Income Planning (income.html) — withdrawal mix, MAGI planning, ACA cliff
- EMR Analysis (index.html) — effective marginal rate sweep chart
- Tax Detail (tax.html) — point-in-time federal + Ohio tax breakdown
- Scenarios (scenarios.html) — save/load/export/import named plans
- Accounts (accounts.html) — account inventory CRUD + bulk CSV update

## Services
- federal_tax — 2025/2026 brackets, ordinary + preferential stacking
- ohio_tax — 2025/2026 Ohio tax, exemptions, retirement credit
- social_security — SS taxability, torpedo calculation
- emr — effective marginal rate sweep, all components
- aca — ACA subsidy from schedule-based interpolation, cliff detection
- total_cost — combines tax EMR + ACA subsidy loss
- accounts — account inventory CRUD (taxable/traditional/roth/hsa)
- scenarios — save/load/export/import named planning scenarios
- data_loader — shared bracket/threshold data loading

## Key Design Decisions
- Single filer only (MFJ deferred)
- Tax years 2025 and 2026 supported
- Profile data in profile/ directory (gitignored)
- App data in data/ directory (committed)
- Specs in specs/ directory

## Current State
- Tests: 529 passing, 97%+ coverage
- CI: ruff, mypy, pytest, bandit, pip-audit on every push

I want to design: [FEATURE NAME]

Here are my initial thoughts: [YOUR IDEAS]
```

**Recommended spec files to upload:** specs most related to the new feature
(e.g. for a new page: frontend_emr.md and frontend_tax.md as style reference)

---

## Build Session (spec already written)

```
I'm working on a Python/FastAPI retirement income planning application.

GitHub: https://github.com/rdsteele/retirement-income-planner
Tech stack: FastAPI, vanilla JS, Plotly, local JSON file storage, Python 3.12+

Pages: Income Planning, EMR Analysis, Tax Detail, Scenarios, Accounts
Services: federal_tax, ohio_tax, social_security, emr, aca, total_cost,
          accounts, scenarios, data_loader
Tests: 529 passing (update this number before each session)
Python 3.12+, single filer only, tax years 2025/2026

Here is the spec for what I want to build today:
[UPLOAD SPEC FILE]

Current test count: 529. All must still pass.
Please read the spec carefully before writing any code.
```

**Recommended spec files to upload:** the spec for the feature being built,
plus any related specs it depends on.

---

## Debug / Review Session

```
I'm working on a Python/FastAPI retirement income planning application.

GitHub: https://github.com/rdsteele/retirement-income-planner
Tech stack: FastAPI, vanilla JS, Plotly, local JSON file storage, Python 3.12+

Pages: Income Planning, EMR Analysis, Tax Detail, Scenarios, Accounts
Services: federal_tax, ohio_tax, social_security, emr, aca, total_cost,
          accounts, scenarios, data_loader
Tests: 529 passing
Python 3.12+

I'm seeing this issue: [DESCRIPTION OF PROBLEM]

Steps to reproduce: [STEPS]

Expected behavior: [WHAT SHOULD HAPPEN]
Actual behavior: [WHAT IS HAPPENING]
```

**Recommended files to upload:** the spec for the relevant feature, plus
any source files directly related to the issue.

---

## Spec Review / Audit Session

```
I'm working on a Python/FastAPI retirement income planning application.

GitHub: https://github.com/rdsteele/retirement-income-planner
Tests: 529 passing

I want to audit the code against the specs to find any discrepancies,
missing coverage, or areas where the implementation has drifted from
the design.

Please review the uploaded spec and identify:
1. Any spec requirements not reflected in the implementation
2. Any implementation behavior not covered by the spec
3. Any inconsistencies between the spec and actual behavior
4. Suggested spec updates to reflect current implementation
```

**Recommended files to upload:** the spec(s) to audit, plus relevant
source files from services/ and api/

---

## Notes

- Always upload relevant spec files — they provide design context efficiently
- Specs are in the specs/ directory of the repo
- Update the test count before each session (run: pytest -q | tail -1)
- Profile data (accounts, scenarios) is in profile/ and gitignored
- App config and bracket data is in data/ and committed
- All pages use vanilla JS, no frameworks
- Plotly is served locally from api/static/plotly-2.26.0.min.js
