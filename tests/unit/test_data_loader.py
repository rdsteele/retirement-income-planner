"""Unit tests for the config-driven helpers in services/data_loader.py.

load_config is mocked; no file I/O.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from services.data_loader import (
    get_default_sweep_ceiling_bracket_rate,
    get_default_sweep_step,
    get_planning_bracket_rates,
    require_supported_filing_status,
    supported_filing_statuses,
)

_CONFIG = {
    "filing_statuses": [
        {"value": "alpha", "label": "Alpha"},
        {"value": "beta", "label": "Beta"},
    ],
    "planning_bracket_rates": ["0.11", "0.33"],
    "default_sweep_ceiling_bracket_rate": "0.33",
    "sweep_step_default": 250,
}


@pytest.fixture(autouse=True)
def _mock_config():
    with patch("services.data_loader.load_config", return_value=_CONFIG):
        yield


def test_supported_filing_statuses_come_from_config():
    assert supported_filing_statuses() == ["alpha", "beta"]


def test_require_accepts_configured_status():
    require_supported_filing_status("beta")  # does not raise


def test_require_rejects_unconfigured_status():
    with pytest.raises(ValueError, match="Unsupported filing status: 'single'"):
        require_supported_filing_status("single")


def test_planning_bracket_rates_are_decimals_from_config():
    assert get_planning_bracket_rates() == [Decimal("0.11"), Decimal("0.33")]


def test_default_sweep_ceiling_bracket_rate_from_config():
    assert get_default_sweep_ceiling_bracket_rate() == Decimal("0.33")


def test_default_sweep_step_from_config():
    assert get_default_sweep_step() == Decimal("250")
