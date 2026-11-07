"""Shared data-loading functions for the services layer.

Each function loads a JSON file from the data/ directory and caches the result
so the file is read only once per process. Services import from here instead of
defining their own loaders.
"""

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_BRACKETS_DIR = _DATA_DIR / "brackets"
_DEDUCTIONS_DIR = _DATA_DIR / "deductions"
_SS_PATH = _DATA_DIR / "ss_thresholds.json"
_CONFIG_PATH = _DATA_DIR / "config.json"


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
def load_aged_deduction_data(tax_year: int) -> dict:
    path = _DEDUCTIONS_DIR / f"aged_{tax_year}.json"
    if not path.exists():
        raise ValueError(f"No age deduction data for tax year: {tax_year}")
    with path.open() as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_ss_data() -> dict:
    with _SS_PATH.open() as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_config() -> dict:
    with _CONFIG_PATH.open() as f:
        return json.load(f)


def supported_filing_statuses() -> list[str]:
    """Return the filing status values the application supports (from config.json)."""
    return [status["value"] for status in load_config()["filing_statuses"]]


def filer_count(filing_status: str) -> int:
    """Return how many people file on a return of this status (from config.json)."""
    require_supported_filing_status(filing_status)
    for status in load_config()["filing_statuses"]:
        if status["value"] == filing_status:
            return int(status["filers"])
    raise ValueError(f"Unsupported filing status: {filing_status!r}")


def require_supported_filing_status(filing_status: str) -> None:
    """Raise ValueError unless the filing status is configured."""
    if filing_status not in supported_filing_statuses():
        raise ValueError(f"Unsupported filing status: {filing_status!r}")


def get_provisional_income_benefit_rate() -> Decimal:
    """Return the fraction of SS benefits counted in provisional income (ss_thresholds.json)."""
    return Decimal(load_ss_data()["provisional_income_benefit_rate"])


def get_planning_bracket_rates() -> list[Decimal]:
    """Return the ordinary bracket rates the planner reports distances to."""
    return [Decimal(rate) for rate in load_config()["planning_bracket_rates"]]


def get_default_sweep_ceiling_bracket_rate() -> Decimal:
    """Return the ordinary bracket rate whose upper bound is the default sweep ceiling."""
    return Decimal(load_config()["default_sweep_ceiling_bracket_rate"])


def get_default_sweep_step() -> Decimal:
    return Decimal(str(load_config()["sweep_step_default"]))
