# Retirement Income Planning

A FastAPI web application for modeling retirement income scenarios, including
tax bracket analysis, Social Security timing, and withdrawal strategies.

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