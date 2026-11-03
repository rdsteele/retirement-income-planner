# Scenario Test: ordinary-rate attribution is exact at bracket edges
#
# Single filer, tax year 2026 (standard deduction 16,100; 10% to 12,400, 12% to 50,400,
# 22% to 105,700 of taxable income). Inputs: interest 40, non-qualified dividends 1,410,
# qualified dividends 2,500, other investment income 1,600, IRA 2,680, LTCG 37,447, and
# an HSA adjustment of 5,400.
#
#   fixed ordinary income      = 40 + 1,410 + 2,680 + 1,600       = 5,730
#   deductions that shelter it = 16,100 + 5,400                   = 21,500
#   -> the deduction is used up after 21,500 - 5,730              = 15,770 of added income
#   -> a bracket starts where taxable ordinary income reaches its lower bound:
#        10% from  15,770 + 0       = 15,770
#        12% from  15,770 + 12,400  = 28,170
#        22% from  15,770 + 50,400  = 66,170
#        24% from  15,770 + 105,700 = 121,470
#
# Before this fix the rate for a point was taken from its lower end, so a bracket was
# reported one sweep step late (22% at 66,200), and the first 10% label appeared up to 500
# early (15,300) because tax 500 dollars ahead was already non-zero.

from decimal import Decimal

import pytest

from services.emr import SweepMode, calculate_emr, compute_planning_signals
from services.income_inputs import IncomeInputs

_INCOME = IncomeInputs(
    interest=Decimal("40"),
    ordinary_dividends=Decimal("1410"),
    qualified_dividends=Decimal("2500"),
    ira_distributions=Decimal("2680"),
    other_investment_ordinary=Decimal("1600"),
    fixed_ltcg=Decimal("37447"),
    above_the_line_adjustments=Decimal("5400"),
)


@pytest.fixture(scope="module")
def result():
    return calculate_emr(
        income=_INCOME,
        sweep_mode=SweepMode.ORDINARY,
        filing_status="single",
        tax_year=2026,
        sweep_floor=Decimal("0"),
        sweep_ceiling=Decimal("130000"),
        sweep_step=Decimal("100"),
    )


def _rate_at(result, income: str) -> Decimal:
    point = next(p for p in result.points if p.income == Decimal(income))
    return point.emr_ordinary


class TestOrdinaryRateStartsAtTheExactBoundary:
    @pytest.mark.parametrize(
        ("income", "rate"),
        [
            ("15700", "0"),  # still sheltered by the deduction
            ("15770", "0.10"),  # deduction used up: the next dollar is taxed at 10%
            ("28100", "0.10"),
            ("28170", "0.12"),
            ("66100", "0.12"),
            ("66170", "0.22"),
            ("121400", "0.22"),
            ("121470", "0.24"),
        ],
    )
    def test_rate_at_the_sweep_point(self, result, income, rate):
        assert _rate_at(result, income) == Decimal(rate)

    def test_no_ordinary_rate_before_the_deduction_is_used_up(self, result):
        early = [p for p in result.points if p.income < Decimal("15770")]
        assert all(p.emr_ordinary == Decimal("0") for p in early)

    def test_a_boundary_point_exists_for_each_bracket_start(self, result):
        incomes = {p.income for p in result.points}
        assert {Decimal(x) for x in ("15770", "28170", "66170", "121470")} <= incomes


class TestDistancesToBracketRates:
    @pytest.fixture(scope="class")
    def distances(self, result):
        signals = compute_planning_signals(result, income=_INCOME, variable_ordinary=Decimal("0"))
        return {d.rate: d.distance for d in signals.bracket_distances}

    def test_distance_to_22_percent_is_the_exact_boundary(self, distances):
        assert distances[Decimal("0.22")] == Decimal("66170")

    def test_distance_to_24_percent_is_the_exact_boundary(self, distances):
        assert distances[Decimal("0.24")] == Decimal("121470")
