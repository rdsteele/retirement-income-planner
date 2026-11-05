# Scenario Test: federal data file matches the published inflation adjustments
#
# Source: IRS Rev. Proc. 2026-35, sections 3.01 (tax rate tables), 3.03 (maximum capital
# gains rate amounts) and 3.02 standard deduction table. Each bracket's published tax
# amount is the cumulative tax at its lower bound, which cross-checks the upper bounds.
#
#   single tops: 12,800 / 52,025 / 109,125 / 208,325 / 264,550 / 661,375
#   joint tops:  25,600 / 104,050 / 218,250 / 416,650 / 529,100 / 793,650
#   published tax at the 37% bound: single 199,237.75; joint 213,290.50
#   zero-rate limit: single 51,050, joint 102,100; 15% limit: 563,200 / 633,600
#   standard deduction: single 16,600, joint 33,200
#
# IRMAA thresholds are not in the file yet: CMS has not published that table.

from decimal import Decimal

import pytest

from services.data_loader import load_federal_data

D = Decimal
_RATES = [D(r) for r in ("0.10", "0.12", "0.22", "0.24", "0.32", "0.35", "0.37")]
_TOPS = {
    "single": [12800, 52025, 109125, 208325, 264550, 661375],
    "mfj": [25600, 104050, 218250, 416650, 529100, 793650],
}
_TAX_AT_TOP = {"single": D("199237.75"), "mfj": D("213290.50")}
_PREFERENTIAL_TOPS = {"single": [51050, 563200], "mfj": [102100, 633600]}
_STANDARD_DEDUCTION = {"single": 16600, "mfj": 33200}


@pytest.mark.parametrize("status", ["single", "mfj"])
def test_ordinary_bracket_bounds(status):
    brackets = load_federal_data(2027)["ordinary"][status]
    assert [D(b["rate"]) for b in brackets] == _RATES
    assert [D(b["to"]) for b in brackets[:-1]] == [D(t) for t in _TOPS[status]]
    assert brackets[-1]["to"] is None


@pytest.mark.parametrize("status", ["single", "mfj"])
def test_brackets_are_contiguous_and_reach_published_tax(status):
    brackets = load_federal_data(2027)["ordinary"][status]
    tax = D(0)
    for lower, upper in zip(brackets, brackets[1:]):
        assert upper["from"] == lower["to"]
        tax += (D(lower["to"]) - D(lower["from"])) * D(lower["rate"])
    assert tax == _TAX_AT_TOP[status]


@pytest.mark.parametrize("status", ["single", "mfj"])
def test_preferential_and_standard_deduction(status):
    data = load_federal_data(2027)
    pref = data["preferential"][status]
    assert [D(b["to"]) for b in pref[:-1]] == [D(t) for t in _PREFERENTIAL_TOPS[status]]
    assert D(data["standard_deduction"][status]) == D(_STANDARD_DEDUCTION[status])
