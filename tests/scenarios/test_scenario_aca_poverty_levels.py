# Scenario Test: ACA poverty-level data and the 400% cliff
#
# The premium tax credit for a coverage year uses the poverty guidelines published the
# year BEFORE (Treas. Reg. 1.36B-1(h)): coverage in 2026 uses the 2025 guidelines and
# coverage in 2025 uses the 2024 guidelines. Source: HHS ASPE poverty guidelines, 48
# contiguous states and DC.
#
#   2024 guidelines: one person 15,060; two people 20,440
#   2025 guidelines: one person 15,650; two people 21,150
#
# A joint return of a couple counts two people. The 400% cliff for coverage in 2026:
#   single: 4 x 15,650 = 62,600
#   joint:  4 x 21,150 = 84,600

import json
from decimal import Decimal
from pathlib import Path

import pytest

from services.aca import calculate_aca_subsidy

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "aca"

_POVERTY_LEVELS = {
    2025: {"single": 15060, "mfj": 20440},
    2026: {"single": 15650, "mfj": 21150},
}


def _fpl(year: int) -> dict:
    return json.loads((_DATA / f"aca_{year}.json").read_text())["fpl_100pct"]


@pytest.mark.parametrize(
    ("year", "status"), [(y, s) for y, by_status in _POVERTY_LEVELS.items() for s in by_status]
)
def test_poverty_level_is_the_prior_years_guideline(year, status):
    assert _fpl(year)[status] == _POVERTY_LEVELS[year][status]


@pytest.mark.parametrize(("status", "cliff"), [("single", "62600"), ("mfj", "84600")])
def test_2026_cliff_is_four_times_the_poverty_level(status, cliff):
    assert Decimal(cliff) == 4 * Decimal(_POVERTY_LEVELS[2026][status])
    result = calculate_aca_subsidy(magi=Decimal("50000"), filing_status=status, tax_year=2026)
    assert result.cliff_magi == Decimal(cliff)
