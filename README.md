# Retirement Income Planning

A FastAPI web application for modeling retirement income and tax planning. Supports federal and state tax calculations, Social Security taxability analysis, marginal effective tax rate (MER) calculations, and multi-stream annual income planning.

## Requirements

- Python 3.12+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running

```bash
uvicorn api.main:app --reload
```

## Testing

```bash
pytest
```