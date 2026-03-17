"""Unit tests for services/total_cost.py.

Tests cover:
1. include_aca=False produces identical results to calculate_emr()
2. ACA MAGI computed correctly at each sweep point
3. emr_aca=0 below/above cliff, spike at cliff
4. total_cost_emr = emr + emr_aca at all points
5. Cliff boundary point inserted at correct sweep_value
6. ORDINARY and PREFERENTIAL modes both compute cliff correctly
"""

from decimal import Decimal
from typing import TypedDict

from services.emr import SweepMode, calculate_emr
from services.total_cost import calculate_total_cost

D = Decimal


class _BaseKwargs(TypedDict):
    pension: Decimal
    interest: Decimal
    ordinary_dividends: Decimal
    ira_distributions: Decimal
    ss_benefit: Decimal
    qualified_dividends: Decimal
    fixed_ltcg: Decimal
    tax_exempt_interest: Decimal
    above_the_line_adjustments: Decimal
    additional_deductions: Decimal
    sweep_mode: SweepMode
    filing_status: str
    tax_year: int
    sweep_floor: Decimal
    sweep_ceiling: Decimal
    sweep_step: Decimal


# ---------------------------------------------------------------------------
# Shared scenario — 2026 single filer matching spec worked example
# ---------------------------------------------------------------------------

_BASE: _BaseKwargs = {
    "pension": D("1596"),
    "interest": D("3353"),
    "ordinary_dividends": D("228"),
    "ira_distributions": D("0"),
    "ss_benefit": D("0"),
    "qualified_dividends": D("2594"),
    "fixed_ltcg": D("21819"),
    "tax_exempt_interest": D("0"),
    "above_the_line_adjustments": D("5300"),
    "additional_deductions": D("23"),
    "sweep_mode": SweepMode.ORDINARY,
    "filing_status": "single",
    "tax_year": 2026,
    "sweep_floor": D("0"),
    "sweep_ceiling": D("70000"),
    "sweep_step": D("1000"),
}

_APTC_MONTHLY = D("520")
_APTC_ANNUAL = _APTC_MONTHLY * 12  # 6240
_CLIFF_MAGI = D("62600")


# ---------------------------------------------------------------------------
# 1. include_aca=False — identical to calculate_emr()
# ---------------------------------------------------------------------------

class TestNoAca:
    def setup_method(self):
        self.tc = calculate_total_cost(**_BASE, include_aca=False)
        self.emr = calculate_emr(
            pension=_BASE["pension"],
            interest=_BASE["interest"],
            ordinary_dividends=_BASE["ordinary_dividends"],
            ira_distributions=_BASE["ira_distributions"],
            ss_benefit=_BASE["ss_benefit"],
            qualified_dividends=_BASE["qualified_dividends"],
            fixed_ltcg=_BASE["fixed_ltcg"],
            tax_exempt_interest=_BASE["tax_exempt_interest"],
            above_the_line_adjustments=_BASE["above_the_line_adjustments"],
            additional_deductions=_BASE["additional_deductions"],
            sweep_mode=_BASE["sweep_mode"],
            filing_status=_BASE["filing_status"],
            tax_year=_BASE["tax_year"],
            sweep_floor=_BASE["sweep_floor"],
            sweep_ceiling=_BASE["sweep_ceiling"],
            sweep_step=_BASE["sweep_step"],
        )

    def test_same_number_of_points(self):
        assert len(self.tc.points) == len(self.emr.points)

    def test_income_values_match(self):
        tc_incomes = [p.income for p in self.tc.points]
        emr_incomes = [p.income for p in self.emr.points]
        assert tc_incomes == emr_incomes

    def test_total_tax_matches(self):
        for tc_p, emr_p in zip(self.tc.points, self.emr.points):
            assert tc_p.total_tax == emr_p.total_tax, f"Mismatch at income={tc_p.income}"

    def test_emr_matches(self):
        for tc_p, emr_p in zip(self.tc.points, self.emr.points):
            assert tc_p.emr == emr_p.emr, f"Mismatch at income={tc_p.income}"

    def test_all_aca_fields_zero(self):
        for p in self.tc.points:
            assert p.aca_magi == D("0")
            assert p.aptc_annual == D("0")
            assert p.aca_subsidy_loss == D("0")
            assert p.emr_aca == D("0")

    def test_total_cost_emr_equals_emr(self):
        for p in self.tc.points:
            assert p.total_cost_emr == p.emr

    def test_result_aca_fields_zero(self):
        assert self.tc.aca_cliff_magi == D("0")
        assert self.tc.aptc_annual_max == D("0")
        assert self.tc.cliff_sweep_value == D("0")


# ---------------------------------------------------------------------------
# 2. ACA MAGI computed correctly at each sweep point (ORDINARY mode)
# ---------------------------------------------------------------------------

class TestAcaMagi:
    def setup_method(self):
        self.tc = calculate_total_cost(**_BASE, include_aca=True)
        self.fixed_ordinary = (
            _BASE["pension"] + _BASE["interest"]
            + _BASE["ordinary_dividends"] + _BASE["ira_distributions"]
        )

    def test_aca_magi_formula_ordinary_mode(self):
        """aca_magi = fixed_ordinary + qd + ltcg + sweep_value + ss_taxable - atl_adj + tei"""
        for p in self.tc.points:
            expected = (
                self.fixed_ordinary
                + _BASE["qualified_dividends"]
                + _BASE["fixed_ltcg"]
                + p.income
                + p.ss_taxable
                - _BASE["above_the_line_adjustments"]
                + _BASE["tax_exempt_interest"]
            )
            assert p.aca_magi == expected, f"MAGI mismatch at income={p.income}"

    def test_aca_magi_increases_with_income(self):
        """ACA MAGI should generally increase as sweep income increases."""
        magis = [p.aca_magi for p in self.tc.points]
        assert magis[-1] > magis[0]


# ---------------------------------------------------------------------------
# 3. emr_aca=0 below cliff, spike at cliff, 0 above cliff
# ---------------------------------------------------------------------------

class TestEmrAca:
    def setup_method(self):
        self.tc = calculate_total_cost(**_BASE, include_aca=True)
        self.cliff_magi = self.tc.aca_cliff_magi

    def test_emr_aca_nonneg_below_cliff(self):
        # With schedule-based ACA, gradual slope contributes a positive emr_aca
        # below the cliff; it is never negative.
        for p in self.tc.points:
            if p.aca_magi < self.cliff_magi:
                assert p.emr_aca >= D("0"), f"Negative emr_aca at income={p.income}, magi={p.aca_magi}"

    def test_emr_aca_spike_at_cliff(self):
        cliff_points = [p for p in self.tc.points if p.aca_magi == self.cliff_magi]
        assert cliff_points, "No point found exactly at cliff MAGI"
        for p in cliff_points:
            expected_spike = _APTC_ANNUAL / D("1000")
            assert p.emr_aca == expected_spike, f"Expected {expected_spike} at cliff, got {p.emr_aca}"

    def test_emr_aca_zero_above_cliff(self):
        for p in self.tc.points:
            if p.aca_magi > self.cliff_magi:
                assert p.emr_aca == D("0"), f"Expected 0 above cliff at income={p.income}"

    def test_aptc_zero_above_cliff(self):
        for p in self.tc.points:
            if p.aca_magi > self.cliff_magi:
                assert p.aptc_annual == D("0"), f"Expected aptc=0 above cliff at income={p.income}"

    def test_aptc_zero_at_and_above_cliff(self):
        # Schedule-based APTC varies by MAGI below cliff; zero at and above cliff.
        for p in self.tc.points:
            if p.aca_magi >= self.cliff_magi:
                assert p.aptc_annual == D("0"), f"Expected 0 at/above cliff, got {p.aptc_annual} at magi={p.aca_magi}"


# ---------------------------------------------------------------------------
# 4. total_cost_emr = emr + emr_aca at all points
# ---------------------------------------------------------------------------

class TestTotalCostEmr:
    def setup_method(self):
        self.tc = calculate_total_cost(**_BASE, include_aca=True)

    def test_total_cost_emr_equals_emr_plus_emr_aca(self):
        for p in self.tc.points:
            assert p.total_cost_emr == p.emr + p.emr_aca, (
                f"total_cost_emr mismatch at income={p.income}"
            )


# ---------------------------------------------------------------------------
# 5. Cliff boundary point inserted at correct sweep_value
# ---------------------------------------------------------------------------

class TestCliffBoundaryInsertion:
    def setup_method(self):
        self.tc = calculate_total_cost(**_BASE, include_aca=True)

    def test_cliff_sweep_value_in_result(self):
        assert self.tc.cliff_sweep_value > D("0")

    def test_cliff_boundary_point_exists_in_sweep(self):
        """The sweep must include a point at the cliff sweep_value."""
        incomes = [p.income for p in self.tc.points]
        assert self.tc.cliff_sweep_value in incomes, (
            f"cliff_sweep_value={self.tc.cliff_sweep_value} not in sweep points"
        )

    def test_cliff_boundary_point_has_magi_at_cliff(self):
        """The point at cliff_sweep_value should have aca_magi == cliff_magi."""
        for p in self.tc.points:
            if p.income == self.tc.cliff_sweep_value:
                assert p.aca_magi == self.tc.aca_cliff_magi, (
                    f"Expected magi={self.tc.aca_cliff_magi}, got {p.aca_magi}"
                )
                break

    def test_result_cliff_magi_correct(self):
        assert self.tc.aca_cliff_magi == _CLIFF_MAGI

    def test_aptc_annual_max_set(self):
        # _BASE floor MAGI = fixed_ordinary + qd + ltcg - atl_adj
        #   = 5177 + 2594 + 21819 - 5300 = 24290
        # 24290 is between schedule points (22000, 972) and (25000, 941).
        # fraction = (24290-22000)/(25000-22000) = 2290/3000
        # monthly = 972 + (2290/3000)*(941-972) = 948.3367 → annual = round(11380.04) = 11380
        assert self.tc.aptc_annual_max == D("11380")


# ---------------------------------------------------------------------------
# 6. PREFERENTIAL mode cliff boundary computed correctly
# ---------------------------------------------------------------------------

class TestPreferentialMode:
    def setup_method(self):
        self.tc = calculate_total_cost(
            pension=D("30000"),
            interest=D("1000"),
            ordinary_dividends=D("0"),
            ira_distributions=D("0"),
            ss_benefit=D("0"),
            qualified_dividends=D("3000"),
            fixed_ltcg=D("10000"),
            tax_exempt_interest=D("0"),
            above_the_line_adjustments=D("5000"),
            additional_deductions=D("0"),
            sweep_mode=SweepMode.PREFERENTIAL,
            filing_status="single",
            tax_year=2026,
            sweep_floor=D("0"),
            sweep_ceiling=D("50000"),
            sweep_step=D("1000"),
            include_aca=True,
        )

    def test_cliff_magi_correct(self):
        assert self.tc.aca_cliff_magi == _CLIFF_MAGI

    def test_cliff_boundary_in_sweep(self):
        incomes = [p.income for p in self.tc.points]
        assert self.tc.cliff_sweep_value in incomes, (
            f"cliff_sweep_value={self.tc.cliff_sweep_value} not in sweep"
        )

    def test_aca_magi_formula_preferential_mode(self):
        """In PREFERENTIAL mode: aca_magi = fixed_ordinary + qd + ltcg + sweep - atl + tei"""
        fixed_ordinary = D("30000") + D("1000")
        for p in self.tc.points:
            expected = (
                fixed_ordinary
                + D("3000")   # qualified_dividends
                + D("10000")  # fixed_ltcg
                + p.income    # sweep_value (preferential)
                + p.ss_taxable
                - D("5000")   # above_the_line_adjustments
                + D("0")      # tax_exempt_interest
            )
            assert p.aca_magi == expected, f"MAGI mismatch at income={p.income}"

    def test_total_cost_emr_equals_emr_plus_emr_aca(self):
        for p in self.tc.points:
            assert p.total_cost_emr == p.emr + p.emr_aca


# ---------------------------------------------------------------------------
# 7. cliff_sweep_value formula — fixed_ltcg and qualified_dividends subtracted
#    in both ORDINARY and PREFERENTIAL modes
# ---------------------------------------------------------------------------

class TestCliffSweepValueFormula:
    """Verify cliff_sweep_value = cliff_magi - fixed_ordinary - qd - ltcg
    - ss_taxable_floor + atl_adj - tei, regardless of sweep_mode."""

    def test_ordinary_mode_subtracts_fixed_ltcg(self):
        # Worked example from spec:
        # cliff=62600, fixed_ordinary=18927, ss_taxable=0, atl=5400, tei=0
        # ltcg=21819, qd=2693
        # expected = 62600 - 18927 - 2693 - 21819 + 5400 - 0 = 24561
        tc = calculate_total_cost(
            pension=D("18927"),
            qualified_dividends=D("2693"),
            fixed_ltcg=D("21819"),
            above_the_line_adjustments=D("5400"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2026,
            sweep_floor=D("0"),
            sweep_ceiling=D("50000"),
            sweep_step=D("1000"),
            include_aca=True,
        )
        assert tc.cliff_sweep_value == D("24561")

    def test_ordinary_mode_subtracts_qualified_dividends(self):
        # fixed_ltcg=0, qualified_dividends=5000, pension=30000, atl=5000
        # expected = 62600 - 30000 - 5000 - 0 + 5000 - 0 = 32600
        tc = calculate_total_cost(
            pension=D("30000"),
            qualified_dividends=D("5000"),
            above_the_line_adjustments=D("5000"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2026,
            sweep_floor=D("0"),
            sweep_ceiling=D("50000"),
            sweep_step=D("1000"),
            include_aca=True,
        )
        assert tc.cliff_sweep_value == D("32600")

    def test_preferential_mode_same_formula(self):
        # pension=30000, interest=1000, qd=3000, ltcg=10000, atl=5000
        # fixed_ordinary = 31000, ss_taxable_floor = 0
        # expected = 62600 - 31000 - 3000 - 10000 + 5000 - 0 = 23600
        tc = calculate_total_cost(
            pension=D("30000"),
            interest=D("1000"),
            qualified_dividends=D("3000"),
            fixed_ltcg=D("10000"),
            above_the_line_adjustments=D("5000"),
            sweep_mode=SweepMode.PREFERENTIAL,
            filing_status="single",
            tax_year=2026,
            sweep_floor=D("0"),
            sweep_ceiling=D("50000"),
            sweep_step=D("1000"),
            include_aca=True,
        )
        assert tc.cliff_sweep_value == D("23600")
