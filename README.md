# Retirement Income Planner

A local retirement income planning tool for analyzing effective marginal tax
rates, Social Security taxability, and ACA subsidy interactions. Runs entirely
on your machine — no cloud, no accounts, no data leaves your computer.

---

## Features

### EMR Analysis

Visualizes the **effective marginal rate (EMR)** on each additional dollar of
income across a sweep range. Shows how ordinary income, the Social Security tax
torpedo, preferential income stacking, NIIT, and Ohio state tax combine into a
single marginal cost curve.

- Federal tax: 2025 and 2026 brackets, ordinary and preferential income stacking
- Social Security taxability: torpedo calculation across both tiers
- Ohio state tax: 2025 and 2026 rates, personal exemption, retirement income credit
- ACA subsidy cliff: total cost EMR including subsidy loss
- IRMAA reference thresholds
- Interactive Plotly chart — stacked area or lines, adjustable sweep range

---

## Requirements

- Python 3.12 or higher
- pip

---

## Setup

```bash
# Clone the repository
git clone https://github.com/rdsteele/retirement-income-planner.git
cd retirement-income-planner

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Running

```bash
uvicorn api.main:app --reload
```

Open your browser to [http://localhost:8000](http://localhost:8000).

---

## Pages

| Page | URL | Description |
|---|---|---|
| EMR Analysis | `/` | Interactive marginal rate chart |

---

## Project Structure

```
api/              # FastAPI application
  routers/        # API route handlers
  models/         # Pydantic request/response models
  static/         # Frontend HTML/JS
data/             # Tax bracket and threshold data (JSON)
  brackets/       # Federal and Ohio bracket files by year
  aca/            # ACA cliff data by year
services/         # Tax calculation services
specs/            # Design specifications
tests/            # Unit and functional tests
```

---

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=services --cov=api --cov-report=term-missing

# Lint
ruff check .

# Type check
mypy .
```

The CI pipeline (GitHub Actions) runs ruff, mypy, pytest, bandit, and
pip-audit on every push to main.

---

## Tax Year Support

| Tax Year | Federal | Ohio |
|---|---|---|
| 2025 | ✅ | ✅ |
| 2026 | ✅ | ✅ |

---

## Disclaimer

This tool is for personal planning and informational purposes only. It is not
tax advice. Consult a qualified tax professional before making financial
decisions.
