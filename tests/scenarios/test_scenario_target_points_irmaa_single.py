# Scenario Test: target points for a single filer climbing through the IRMAA tiers
#
# Setup: single filer, 40,000 of taxable pension, no Social Security, no investment income,
# no Ohio, no ACA. The sweep adds ordinary income from 0 to 150,000 and the IRMAA
# thresholds are not inflated. Maximum EMR 30%. Only the federal tax and the IRMAA
# surcharge apply, so no ordinary bracket is above the maximum and every costly stretch is
# an IRMAA cliff (the whole year's surcharge on one dollar).
#
# Data used (data files for the planning year):
#   standard deduction 16,100
#   brackets: 10% to 12,400; 12% to 50,400; 22% to 105,700; 24% to 201,775 (taxable income)
#   IRMAA thresholds: 109,000 / 137,000 / 171,000 / 205,000 / 500,000
#   monthly surcharge per person (Part B + Part D):
#     tier 1  81.20 + 14.50 =  95.70   -> 1,148.40 a year
#     tier 2 202.90 + 37.50 = 240.40   -> 2,884.80 a year
#     tier 3 324.60 + 60.40 = 385.00   -> 4,620.00 a year
#
# Targets: the last dollar of sweep income before each cliff. MAGI = 40,000 + sweep, so the
# cliffs sit just above sweep incomes 69,000 / 97,000 / 131,000, plus the sweep's ends.
#
# Federal tax by sweep income (taxable income = 40,000 + sweep - 16,100):
#       0 -> taxable  23,900: 1,240 + 11,500 x 12%                       =  2,620
#  69,000 -> taxable  92,900: 1,240 + 38,000 x 12% + 42,500 x 22%        = 15,150
#  97,000 -> taxable 120,900: 1,240 + 4,560 + 55,300 x 22% + 15,200 x 24% = 21,614
# 131,000 -> taxable 154,900: 1,240 + 4,560 + 12,166 + 49,200 x 24%       = 29,774
# 150,000 -> taxable 173,900: 1,240 + 4,560 + 12,166 + 68,200 x 24%       = 34,334
#
# Legs (cost = tax added + surcharge added, over the width of the leg):
#   0 -> 69,000:       12,530.00 / 69,000 = 0.1816   (no cliff inside)
#   69,000 -> 97,000:   6,464 + 1,148.40 = 7,612.40  / 28,000 = 0.2719 (tier 1 cliff)
#   97,000 -> 131,000:  8,160 + 1,736.40 = 9,896.40  / 34,000 = 0.2911 (tier 2 cliff)
#   131,000 -> 150,000: 4,560 + 1,735.20 = 6,295.20  / 19,000 = 0.3313 -> above 30%, dropped

from decimal import Decimal

from services.emr import SweepMode
from services.income_inputs import IncomeInputs
from services.target_points import calculate_target_points

D = Decimal


def _run(**overrides):
    kwargs = dict(
        income=IncomeInputs(pension=D("40000")),
        filing_status="single",
        tax_year=2026,
        max_rate=D("0.30"),
        sweep_mode=SweepMode.ORDINARY,
        sweep_floor=D("0"),
        sweep_ceiling=D("150000"),
        sweep_step=D("1000"),
        include_irmaa=True,
        irmaa_inflation_rate=D("0"),
    )
    return calculate_target_points(**{**kwargs, **overrides})


def test_targets_sit_just_before_each_irmaa_cliff():
    assert _run().targets == [D("0"), D("69000"), D("97000"), D("131000"), D("150000")]


def test_leg_averages_match_the_hand_calculation():
    legs = _run().legs
    assert [(leg.from_income, leg.to_income) for leg in legs] == [
        (D("0"), D("69000")),
        (D("69000"), D("97000")),
        (D("97000"), D("131000")),
    ]
    assert [leg.average_emr for leg in legs] == [D("0.1816"), D("0.2719"), D("0.2911")]


def test_leg_costs_include_the_surcharge():
    assert [leg.cost for leg in _run().legs] == [D("12530"), D("7612.40"), D("9896.40")]


def test_cliff_legs_are_attributed_to_irmaa():
    assert [leg.causes for leg in _run().legs] == [(), ("irmaa",), ("irmaa",)]


def test_the_last_leg_is_dropped_because_its_cliff_pushes_it_over_the_maximum():
    assert all(leg.to_income != D("150000") for leg in _run().legs)


def test_without_irmaa_the_whole_sweep_is_one_desirable_leg():
    result = _run(include_irmaa=False)
    assert result.targets == [D("0"), D("150000")]
    assert len(result.legs) == 1
    # 34,334 - 2,620 = 31,714 over 150,000
    assert result.legs[0].average_emr == D("0.2114")
