# Scenario Test: ACA MAGI counts the whole Social Security benefit
#
# Source: IRS Publication 974 / Form 8962 instructions. For the premium tax credit,
# modified AGI = AGI + foreign earned income + tax-exempt interest + the NONTAXABLE
# portion of Social Security benefits. AGI already includes the taxable portion, so
# the whole benefit is counted.
#
# Single filer, tax year 2026, standard deduction 16,100. Pension 20,000, SS 24,000.
# Hand-verified:
#   provisional income = 20,000 + 50% x 24,000 = 32,000   (tier 1 threshold 25,000)
#   taxable SS         = 50% x (32,000 - 25,000)         = 3,500
#   AGI                = 20,000 + 3,500                  = 23,500
#   ACA MAGI           = 20,000 + 24,000                 = 44,000   (not 23,500)
#   federal tax        = (23,500 - 16,100) x 10%         = 740
#   APTC schedule      : 40,000 -> 751/mo, 45,000 -> 679/mo
#                        at 44,000: 751 + 0.8 x (679 - 751) = 693.40/mo = 8,320.80 -> 8,321/yr
#   cliff (single)     : 62,600  ->  cliff sweep value = 62,600 - 44,000 = 18,600
#
# Counting only the taxable part (MAGI 23,500) would have overstated the subsidy by
# about 3,100 a year (about 11,478 instead of 8,321).

from decimal import Decimal

import pytest

from services.emr import SweepMode
from services.income_inputs import IncomeInputs
from services.total_cost import calculate_total_cost

_INCOME = IncomeInputs(pension=Decimal("20000"), ss_benefit=Decimal("24000"))


@pytest.fixture
def result():
    return calculate_total_cost(
        income=_INCOME,
        sweep_mode=SweepMode.ORDINARY,
        filing_status="single",
        tax_year=2026,
        sweep_floor=Decimal("0"),
        sweep_ceiling=Decimal("5000"),
        sweep_step=Decimal("5000"),
        include_aca=True,
    )


class TestAcaMagiWithSocialSecurity:
    def test_taxable_social_security(self, result):
        assert result.points[0].ss_taxable == Decimal("3500")

    def test_federal_tax_uses_only_the_taxable_part(self, result):
        assert result.points[0].total_tax == Decimal("740")

    def test_aca_magi_counts_the_whole_benefit(self, result):
        assert result.points[0].aca_magi == Decimal("44000")

    def test_annual_subsidy_at_that_magi(self, result):
        assert result.points[0].aptc_annual == Decimal("8321")

    def test_cliff_magi(self, result):
        assert result.aca_cliff_magi == Decimal("62600")

    def test_cliff_sweep_value(self, result):
        assert result.cliff_sweep_value == Decimal("18600")
