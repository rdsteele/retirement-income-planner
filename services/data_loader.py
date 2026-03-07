"""Shared data-loading functions for the services layer.

Each function loads a JSON file from the data/ directory and caches the result
so the file is read only once per process. Services import from here instead of
defining their own loaders.
"""

import json
from functools import lru_cache
from pathlib import Path

_BRACKETS_DIR = Path(__file__).parent.parent / "data" / "brackets"
_SS_PATH = Path(__file__).parent.parent / "data" / "ss_thresholds.json"


@lru_cache(maxsize=None)
def load_federal_data(tax_year: int) -> dict:
    path = _BRACKETS_DIR / f"federal_{tax_year}.json"
    if not path.exists():
        raise ValueError(f"Unsupported tax year: {tax_year}")
    with path.open() as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_ohio_data(tax_year: int) -> dict:
    path = _BRACKETS_DIR / f"ohio_{tax_year}.json"
    if not path.exists():
        raise ValueError(f"Unsupported tax year: {tax_year}")
    with path.open() as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_ss_data() -> dict:
    with _SS_PATH.open() as f:
        return json.load(f)
