# Scenario Test: Single filer 2026 — standard deduction exceeds ordinary income
#
# Source: Retirement Researcher Tax Calculator ("Tax Map", initial position).
# Purpose: Regression anchor for unused deduction offsetting preferential income.
#
# Inputs (2026, single, standard deduction $16,100):
#   interest 40, IRA 2,680, other investment ordinary 1,600, non-qualified
#   dividends 1,410, qualified dividends 2,500, LTCG 37,447, HSA adjustment 5,400.
#
# RR results: AGI 40,277; ordinary AGI portion 330; taxable income 24,177 (all
# preferential); federal tax 0.
# Previously this tool reported taxable preferential income of 39,947 because the
# unused deduction (16,100 - 330 = 15,770) was discarded rather than applied to
# preferential income.

from decimal import Decimal

import pytest

from services.emr import SweepMode, calculate_emr, compute_planning_signals
from services.federal_tax import calculate_federal_tax, split_taxable_income
from services.income_inputs import IncomeInputs

_INCOME = IncomeInputs(
    pension=Decimal("1600"),
    interest=Decimal("40"),
    ordinary_dividends=Decimal("1410"),
    ira_distributions=Decimal("2680"),
    qualified_dividends=Decimal("2500"),
    fixed_ltcg=Decimal("37447"),
    above_the_line_adjustments=Decimal("5400"),
)
_CONTEXT = dict(filing_status="single", tax_year=2026)


class TestRRScenarioTaxableIncomeSplit:
    @pytest.fixture
    def split(self):
        return split_taxable_income(Decimal("330"), Decimal("39947"), Decimal("16100"))

    def test_taxable_ordinary(self, split):
        assert split[0] == Decimal("0")

    def test_taxable_preferential(self, split):
        assert split[1] == Decimal("24177")

    def test_federal_tax_is_zero(self, split):
        result = calculate_federal_tax(split[0], split[1], "single", 2026)
        assert result.total_tax == Decimal("0")


class TestRRScenarioEMRSweep:
    @pytest.fixture
    def result(self):
        return calculate_emr(
            income=_INCOME,
            **_CONTEXT,
            sweep_mode=SweepMode.ORDINARY,
            sweep_floor=Decimal("0"),
            sweep_ceiling=Decimal("2000"),
        )

    def test_floor_point_taxable_ordinary(self, result):
        assert result.points[0].taxable_ordinary == Decimal("0")

    def test_floor_point_taxable_preferential(self, result):
        assert result.points[0].taxable_preferential == Decimal("24177")

    def test_floor_point_total_tax(self, result):
        assert result.points[0].total_tax == Decimal("0")

    def test_ltcg_0pct_remaining_uses_total_taxable_income(self, result):
        signals = compute_planning_signals(result, income=_INCOME, variable_ordinary=Decimal("0"))
        # 2026 single 0% LTCG ceiling 49,450 - taxable income 24,177
        assert signals.ltcg_0pct_remaining == Decimal("25273")
