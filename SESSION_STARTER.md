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
- Income Planning (income.html) — withdrawal mix, MAGI planning, ACA cliff [default /]
- EMR Analysis (emr.html) — effective marginal rate sweep chart [/emr]
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
- Tests: 530 passing, 97%+ coverage
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
Tests: 530 passing (update this number before each session)
Python 3.12+, single filer only, tax years 2025/2026

Here is the spec for what I want to build today:
[UPLOAD SPEC FILE]

Current test count: 530. All must still pass.
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
Tests: 530 passing
Python 3.12+

I'm seeing this issue: [DESCRIPTION OF PROBLEM]

Steps to reproduce: [STEPS]

Expected behavior: [WHAT SHOULD HAPPEN]
Actual behavior: [WHAT IS HAPPENING]
```

**Recommended files to upload:** the spec for the relevant feature, plus
any source files directly related to the issue.

---

## Spec Audit Session (chat, not Claude Code)

```
I'm working on a Python/FastAPI retirement income planning application.

GitHub: https://github.com/rdsteele/retirement-income-planner
Tests: 530 passing

Fetch the spec at [SPEC_URL] and review it against the code pasted below.

Identify and format as a numbered list:
1. Spec requirements not reflected in the implementation
2. Implementation behavior not covered by the spec
3. Inconsistencies between spec and actual behavior
4. Suggested spec updates to reflect current implementation

For each finding: describe the discrepancy, cite the spec section and
code location, and recommend whether to update the spec or the code.

[PASTE CODE HERE]
```

**Spec raw URLs:**
```
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/aca.md
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/emr.md
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/fastapi_emr_route.md
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/federal_tax.md
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/frontend_emr.md
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/ohio_tax.md
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/social_security.md
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/specs/total_cost.md
```

**Service raw URLs:**
```
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/services/aca.py
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/services/emr.py
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/services/federal_tax.py
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/services/ohio_tax.py
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/services/social_security.py
https://raw.githubusercontent.com/rdsteele/retirement-income-planner/main/services/total_cost.py
```

---

## Notes

- Always upload relevant spec files — they provide design context efficiently
- Specs are in the specs/ directory of the repo
- Update the test count before each session (run: pytest -q | tail -1)
- Profile data (accounts, scenarios) is in profile/ and gitignored
- App config and bracket data is in data/ and committed
- All pages use vanilla JS, no frameworks
- Plotly is served locally from api/static/plotly-2.26.0.min.js
- Default landing page is Income Planning (/). EMR Analysis is at /emr.
