# Scenario Test: additional standard deduction for filers aged 65 or older
#
# Source: IRS Rev. Proc. 2024-40 (2025), 2025-32 (2026) and 2026-35 (2027), the "Aged or
# blind" item under section 63(f). The amount is per person: the higher unmarried amount
# applies to a single filer, the lower amount to each spouse on a joint return.
#
#   2025: 2,000 single; 1,600 per spouse
#   2026: 2,050 single; 1,650 per spouse
#   2027: 2,100 single; 1,700 per spouse
#
# Hand-checked 2026 cases (pension is the only income, so AGI equals the pension):
#   Single, 66:        50,000 - (16,100 + 2,050) = 31,850 taxable
#                      1,240 + 12% x (31,850 - 12,400) = 3,574
#   Joint, one 65:     80,000 - (32,200 + 1,650) = 46,150 taxable
#                      2,480 + 12% x (46,150 - 24,800) = 5,042
#   Joint, both 65:    80,000 - (32,200 + 3,300) = 44,500 taxable
#                      2,480 + 12% x (44,500 - 24,800) = 4,844
#   Joint, none 65:    80,000 - 32,200 = 47,800 taxable; 2,480 + 12% x 23,000 = 5,240
# Zero ordinary space (income that is sheltered): the whole deduction, e.g. 18,150 single.

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "deductions"
_PUBLISHED = {
    2025: {"single": "2000", "mfj": "1600"},
    2026: {"single": "2050", "mfj": "1650"},
    2027: {"single": "2100", "mfj": "1700"},
}


@pytest.mark.parametrize("year", sorted(_PUBLISHED))
def test_data_matches_the_published_amounts(year):
    stored = json.loads((_DATA / f"aged_{year}.json").read_text())
    assert stored["additional_standard_deduction"] == _PUBLISHED[year]


def _tax(status: str, taxpayer: bool = False, spouse: bool = False, pension: float = 0.0):
    resp = client.post(
        "/api/tax",
        json={
            "filing_status": status,
            "tax_year": 2026,
            "pension": pension,
            "taxpayer_65_plus": taxpayer,
            "spouse_65_plus": spouse,
        },
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.parametrize(
    ("status", "taxpayer", "spouse", "pension", "age_deduction", "taxable", "tax"),
    [
        ("single", True, False, 50000, 2050, 31850, 3574),
        ("mfj", True, False, 80000, 1650, 46150, 5042),
        ("mfj", True, True, 80000, 3300, 44500, 4844),
        ("mfj", False, False, 80000, 0, 47800, 5240),
    ],
)
def test_age_deduction_lowers_taxable_income_and_tax(
    status, taxpayer, spouse, pension, age_deduction, taxable, tax
):
    body = _tax(status, taxpayer, spouse, pension)
    summary = body["inputs_summary"]
    assert summary["age_deduction"] == age_deduction
    assert summary["taxable_ordinary"] == taxable
    assert body["federal"]["total_tax"] == tax


def test_a_spouse_on_a_single_return_is_ignored():
    assert _tax("single", spouse=True, pension=50000)["inputs_summary"]["age_deduction"] == 0


def test_the_sheltered_income_space_includes_the_age_deduction():
    def zero_space(taxpayer: bool) -> float:
        resp = client.post(
            "/api/income-plan/calculate",
            json={
                "filing_status": "single",
                "tax_year": 2026,
                "include_ohio": False,
                "taxpayer_65_plus": taxpayer,
                "sweep_ceiling": 1000,
                "sweep_step": 500,
            },
        )
        return resp.json()["planning_signals"]["zero_ordinary_space"]

    assert zero_space(False) == 16100
    assert zero_space(True) == 18150
