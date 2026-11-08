# Scenario Test: temporary senior deduction for filers aged 65 or older
#
# The 2025 tax law gives $6,000 per person aged 65 or older for tax years 2025 to 2028,
# reduced by 6% of modified AGI over 75,000 (single) or 150,000 (joint). It is claimed on
# top of the standard deduction and the additional standard deduction for age. The
# single age-66 case at 50,000 was checked against the Retirement Researcher (RR) Tax
# Map calculator, which showed a 24,150 deduction (16,100 + 2,050 + 6,000).
#
# 2026 hand-checked cases (income is a pension, so MAGI equals the pension):
#   Single 66, 50,000:  deduction 16,100 + 2,050 + 6,000 = 24,150; taxable 25,850
#                       1,240 + 12% x 13,450 = 2,854                    (matches RR)
#   Single 66, 100,000: senior 6,000 - 6% x 25,000 = 4,500; deduction 22,650; taxable 77,350
#                       5,800 + 22% x 26,950 = 11,729
#   Single 66, 175,000: senior 6,000 - 6% x 100,000 = 0; taxable 156,850
#                       17,966 + 24% x 51,150 = 30,242
#   Joint, both 66, 100,000: senior 12,000; deduction 32,200 + 3,300 + 12,000; taxable 52,500
#                       2,480 + 12% x 27,700 = 5,804
#   Joint, both 66, 200,000: each 6,000 - 6% x 50,000 = 3,000, so senior 6,000; taxable 158,500
#                       11,600 + 22% x 57,700 = 24,294
#   Joint, both 66, 250,000: each 6,000 - 6% x 100,000 = 0; deduction 35,500; taxable 214,500
#                       35,932 + 24% x 3,100 = 36,676                   (matches RR)
#   (The reduction applies to each person's amount, as RR does; a single reduction on the
#   combined 12,000 would leave 6,000 at 250,000. Not checked against the statute text.)
#   Joint, one 66, 150,000: senior 6,000 (at the threshold); deduction 33,850 + 6,000;
#                       taxable 110,150; 11,600 + 22% x 9,350 = 13,657

import pytest
from fastapi.testclient import TestClient

from api.main import app
from services.data_loader import load_senior_deduction_data

client = TestClient(app)


def _tax(status, pension, taxpayer=True, spouse=False, claim=True):
    resp = client.post(
        "/api/tax",
        json={
            "filing_status": status,
            "tax_year": 2026,
            "pension": pension,
            "taxpayer_65_plus": taxpayer,
            "spouse_65_plus": spouse,
            "claim_senior_deduction": claim,
        },
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.parametrize(
    ("status", "pension", "spouse", "senior", "taxable", "tax"),
    [
        ("single", 50000, False, 6000, 25850, 2854),
        ("single", 100000, False, 4500, 77350, 11729),
        ("single", 175000, False, 0, 156850, 30242),
        ("single", 200000, False, 0, 181850, 36242),
        ("mfj", 100000, True, 12000, 52500, 5804),
        ("mfj", 200000, True, 6000, 158500, 24294),
        ("mfj", 250000, True, 0, 214500, 36676),
        ("mfj", 250000, False, 0, 216150, 37072),
        ("mfj", 150000, False, 6000, 110150, 13657),
    ],
)
def test_senior_deduction_and_its_phaseout(status, pension, spouse, senior, taxable, tax):
    body = _tax(status, pension, spouse=spouse)
    assert body["inputs_summary"]["senior_deduction"] == senior
    assert body["inputs_summary"]["taxable_ordinary"] == taxable
    assert body["federal"]["total_tax"] == tax


def test_not_claimed_leaves_only_the_additional_standard_deduction():
    body = _tax("single", 50000, claim=False)
    assert body["inputs_summary"]["senior_deduction"] == 0
    assert body["federal"]["total_tax"] == 3574


def test_nobody_65_gets_no_senior_deduction_even_when_claimed():
    assert _tax("single", 50000, taxpayer=False)["inputs_summary"]["senior_deduction"] == 0


def test_the_data_file_matches_the_law():
    data = load_senior_deduction_data()
    assert (data["first_year"], data["last_year"]) == (2025, 2028)
    assert data["amount_per_person"] == "6000"
    assert data["phaseout_rate"] == "0.06"
    assert data["phaseout_start"] == {"single": "75000", "mfj": "150000"}


def test_the_sweep_starts_with_the_deduction_at_the_starting_income():
    # 50,000 of pension: the sheltered space includes 16,100 + 2,050 + 6,000
    resp = client.post(
        "/api/income-plan/calculate",
        json={
            "filing_status": "single",
            "tax_year": 2026,
            "include_ohio": False,
            "taxpayer_65_plus": True,
            "claim_senior_deduction": True,
            "sweep_ceiling": 1000,
            "sweep_step": 500,
        },
    )
    assert resp.json()["planning_signals"]["zero_ordinary_space"] == 24150
