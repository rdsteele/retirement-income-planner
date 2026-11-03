# Scenario Test: IRMAA MAGI per sweep point
#
# SSA (POMS HI 01101.010): for IRMAA, MAGI = adjusted gross income + tax-exempt interest.
# Unlike the ACA premium tax credit, the nontaxable part of Social Security is NOT added.
# So IRMAA MAGI is AGI plus tax-exempt interest at every sweep point, and it moves with
# the sweep (and, with Social Security, faster than one for one through the torpedo).
#
# Single filer, tax year 2026.
#
# Hand-verified with pension 20,000 and Social Security 24,000 (tier 1 threshold 25,000,
# tier 2 threshold 34,000; provisional income = 20,000 + 12,000 + added income):
#   added 0:       PI 32,000 -> taxable SS 50% x 7,000                   = 3,500
#                  AGI = 20,000 + 3,500                                  = 23,500
#   added 5,000:   PI 37,000 -> taxable SS 4,500 + 85% x 3,000           = 7,050
#                  AGI = 20,000 + 5,000 + 7,050                          = 32,050
#   added 10,000:  PI 42,000 -> taxable SS 4,500 + 85% x 8,000           = 11,300
#                  AGI = 20,000 + 10,000 + 11,300                        = 41,300
# (ACA MAGI at added 0 would be 44,000: it counts all 24,000 of benefits.)

from decimal import Decimal

from services.emr import SweepMode, calculate_emr
from services.income_inputs import IncomeInputs

D = Decimal


def _sweep(income: IncomeInputs, mode: SweepMode = SweepMode.ORDINARY, ceiling: str = "10000"):
    return calculate_emr(
        income=income,
        sweep_mode=mode,
        filing_status="single",
        tax_year=2026,
        sweep_floor=D("0"),
        sweep_ceiling=D(ceiling),
        sweep_step=D("5000"),
    )


def _at(result, added: str):
    return next(p for p in result.points if p.income == D(added))


class TestWithoutSocialSecurity:
    def test_irmaa_magi_is_agi_and_rises_one_for_one(self):
        result = _sweep(IncomeInputs(pension=D("40000")))
        assert all(p.irmaa_magi == D("40000") + p.income for p in result.points)

    def test_tax_exempt_interest_adds(self):
        result = _sweep(IncomeInputs(pension=D("40000"), tax_exempt_interest=D("500")))
        assert _at(result, "0").irmaa_magi == D("40500")

    def test_long_term_gains_and_dividends_count(self):
        result = _sweep(
            IncomeInputs(pension=D("30000"), fixed_ltcg=D("3000"), qualified_dividends=D("2000"))
        )
        assert _at(result, "0").irmaa_magi == D("35000")

    def test_above_the_line_adjustments_reduce_it(self):
        result = _sweep(IncomeInputs(pension=D("40000"), above_the_line_adjustments=D("5400")))
        assert _at(result, "0").irmaa_magi == D("34600")

    def test_preferential_sweep_adds_one_for_one(self):
        result = _sweep(IncomeInputs(pension=D("40000")), mode=SweepMode.PREFERENTIAL)
        assert all(p.irmaa_magi == D("40000") + p.income for p in result.points)


class TestWithSocialSecurity:
    _INCOME = IncomeInputs(pension=D("20000"), ss_benefit=D("24000"))

    def test_only_the_taxable_part_of_social_security_counts(self):
        assert _at(_sweep(self._INCOME), "0").irmaa_magi == D("23500")

    def test_through_the_torpedo_at_5000_added(self):
        assert _at(_sweep(self._INCOME), "5000").irmaa_magi == D("32050")

    def test_through_the_torpedo_at_10000_added(self):
        assert _at(_sweep(self._INCOME), "10000").irmaa_magi == D("41300")

    def test_differs_from_aca_magi_which_counts_the_whole_benefit(self):
        # ACA MAGI at the floor would be 20,000 + 24,000 = 44,000
        assert _at(_sweep(self._INCOME), "0").irmaa_magi != D("44000")
