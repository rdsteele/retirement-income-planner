"""Unit tests for services/emr.py.

All three composed services (federal_tax, social_security, ohio_tax) are mocked.
No real tax calculations are performed. Mock side_effects provide simplified
bracket logic consistent with 2025 single-filer data, enabling verification of
EMR computation, component attribution, boundary insertion, and Ohio toggling.

Test cases are derived from the worked examples in specs/emr.md.
"""

from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import patch

import pytest

from services.common import round_rate, round_tax
from services.emr import EMRResult, SweepMode, calculate_emr
from services.federal_tax import FederalTaxResult
from services.ohio_tax import OhioTaxResult
from services.social_security import SocialSecurityResult


def D(s: str) -> Decimal:
    return Decimal(s)


_ZERO = D("0")
_TWO_PLACES = Decimal("0.01")
_COMPONENT_TOLERANCE = D("0.003")

_SINGLE_ORDINARY_BRACKETS = [
    (D("0"), D("11925"), D("0.10")),
    (D("11925"), D("48475"), D("0.12")),
    (D("48475"), D("103350"), D("0.22")),
    (D("103350"), D("197300"), D("0.24")),
    (D("197300"), D("250525"), D("0.32")),
    (D("250525"), D("626350"), D("0.35")),
]

_SINGLE_PREF_BRACKETS = [
    (D("0"), D("48350"), D("0.00")),
    (D("48350"), D("533400"), D("0.15")),
]


# ---------------------------------------------------------------------------
# Mock side-effect helpers
# ---------------------------------------------------------------------------

def _round2(amount: Decimal) -> Decimal:
    return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _mock_federal_single(ordinary_income, preferential_income,
                         filing_status, tax_year):
    """Simplified single-filer bracket computation matching 2025 data."""
    ord_tax = _ZERO
    remaining = ordinary_income
    rate = D("0.10")
    for b_from, b_to, b_rate in _SINGLE_ORDINARY_BRACKETS:
        if remaining <= _ZERO:
            break
        width = b_to - b_from
        taxed = min(remaining, width)
        if taxed > _ZERO:
            ord_tax += round_tax(taxed * b_rate)
            rate = b_rate
            remaining -= taxed
    if remaining > _ZERO:
        ord_tax += round_tax(remaining * D("0.37"))
        rate = D("0.37")

    pref_tax = _ZERO
    pref_remaining = preferential_income
    stack_base = ordinary_income
    for b_from, b_to, b_rate in _SINGLE_PREF_BRACKETS:
        if pref_remaining <= _ZERO:
            break
        bracket_start = max(stack_base, b_from)
        if bracket_start >= b_to:
            continue
        available = b_to - bracket_start
        taxed = min(pref_remaining, available)
        if taxed > _ZERO:
            pref_tax += round_tax(taxed * b_rate)
            pref_remaining -= taxed
            stack_base += taxed
    if pref_remaining > _ZERO:
        pref_tax += round_tax(pref_remaining * D("0.20"))

    total = ord_tax + pref_tax
    total_income = ordinary_income + preferential_income
    eff = round_rate(total / total_income) if total_income else _ZERO

    return FederalTaxResult(
        ordinary_income_tax=ord_tax,
        preferential_income_tax=pref_tax,
        total_tax=total,
        effective_rate=eff,
        marginal_bracket_rate=rate,
        bracket_breakdown=[],
    )


def _mock_ss_single(ss_benefit, agi_excluding_ss, tax_exempt_interest,
                    filing_status):
    """Simplified single-filer SS taxability matching IRS formula."""
    half_ss = _round2(ss_benefit * D("0.50"))
    provisional = agi_excluding_ss + tax_exempt_interest + half_ss

    if ss_benefit == _ZERO:
        return SocialSecurityResult(provisional, _ZERO, _ZERO, "none")

    tier_1, tier_2 = D("25000"), D("34000")

    if provisional <= tier_1:
        return SocialSecurityResult(provisional, _ZERO, _ZERO, "none")

    if provisional < tier_2:
        amount = _round2(D("0.50") * (provisional - tier_1))
        cap = _round2(D("0.50") * ss_benefit)
        taxable = round_tax(min(amount, cap))
        inc = round_rate(taxable / ss_benefit)
        return SocialSecurityResult(provisional, taxable, inc, "fifty_percent")

    tier_1_range = tier_2 - tier_1
    max_tier_1 = min(
        _round2(D("0.50") * ss_benefit),
        _round2(D("0.50") * tier_1_range),
    )
    tier_2_amount = _round2(D("0.85") * (provisional - tier_2))
    max_taxable = _round2(D("0.85") * ss_benefit)
    taxable = round_tax(min(max_taxable, tier_2_amount + max_tier_1))
    inc = round_rate(taxable / ss_benefit)
    return SocialSecurityResult(provisional, taxable, inc, "eighty_five_percent")


def _mock_ohio(federal_agi, gross_medical_expenses,
               qualifying_retirement_income, ss_taxable_federal, tax_year):
    """Simplified Ohio tax returning a fixed-rate result for EMR testing."""
    ohio_agi = federal_agi - ss_taxable_federal
    pe = D("2400") if ohio_agi <= D("40000") else (
        D("2150") if ohio_agi <= D("80000") else D("1900"))

    medical_floor = round_tax(ohio_agi * D("0.075"))
    med_ded = max(_ZERO, gross_medical_expenses - medical_floor)

    tax_base = max(_ZERO, ohio_agi - pe - med_ded)

    if tax_base <= D("26050"):
        tax_before = _ZERO
    elif tax_base <= D("100000"):
        tax_before = D("342") + round_tax(D("0.0275") * (tax_base - D("26050")))
    else:
        tax_before = D("2394") + round_tax(D("0.03125") * (tax_base - D("100000")))

    credit = _ZERO
    if (ohio_agi - pe) < D("100000") and qualifying_retirement_income > _ZERO:
        if qualifying_retirement_income > D("8000"):
            credit = D("200")
        elif qualifying_retirement_income > D("5000"):
            credit = D("130")
        elif qualifying_retirement_income > D("3000"):
            credit = D("80")
        elif qualifying_retirement_income > D("1500"):
            credit = D("50")
        elif qualifying_retirement_income > D("500"):
            credit = D("25")

    ohio_tax = max(_ZERO, tax_before - credit)
    eff = round_rate(ohio_tax / ohio_agi) if ohio_agi > _ZERO else _ZERO

    return OhioTaxResult(
        ohio_agi=ohio_agi,
        personal_exemption=pe,
        medical_deduction=med_ded,
        ohio_tax_base=tax_base,
        tax_before_credits=tax_before,
        retirement_income_credit=credit,
        ohio_tax=ohio_tax,
        effective_rate=eff,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_point(result: EMRResult, income: Decimal):
    """Return the EMRPoint at exactly the given income, or None."""
    for pt in result.points:
        if pt.income == income:
            return pt
    return None


def _assert_component_sum(pt, tolerance=_COMPONENT_TOLERANCE):
    """Assert EMR component breakdown sums to emr within tolerance."""
    component_sum = (pt.emr_ordinary + pt.emr_ss_torpedo
                     + pt.emr_pref_stacking + pt.emr_niit + pt.emr_ohio)
    diff = abs(pt.emr - component_sum)
    assert diff <= tolerance, (
        f"At income={pt.income}: emr={pt.emr}, component_sum={component_sum}, "
        f"diff={diff}"
    )


_PATCH_FED = "services.emr.calculate_federal_tax"
_PATCH_SS = "services.emr.calculate_social_security_taxability"
_PATCH_OHIO = "services.emr.calculate_ohio_tax"


# ---------------------------------------------------------------------------
# Example A — Ordinary Sweep, No SS
# Pension/interest income in 10%/12% brackets. Preferential stacking at ~27100.
# ---------------------------------------------------------------------------

class TestExampleAOrdinarySweepNoSS:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=D("20000"), interest=D("2000"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("5000"),
            fixed_ltcg=D("10000"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("100"), sweep_ceiling=D("110000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_result_metadata(self):
        assert self.result.sweep_mode == SweepMode.ORDINARY
        assert self.result.filing_status == "single"
        assert self.result.tax_year == 2025

    def test_emr_in_10_bracket(self):
        pt = _find_point(self.result, D("0"))
        assert pt is not None
        assert pt.emr == D("0.1000")
        assert pt.total_tax == D("625")
        assert pt.taxable_ordinary == D("6250")

    def test_emr_in_12_bracket(self):
        pt = _find_point(self.result, D("6000"))
        assert pt is not None
        assert pt.emr == D("0.1200")
        assert pt.total_tax == D("1232")

    def test_emr_stacking_zone(self):
        pt = _find_point(self.result, D("30000"))
        assert pt is not None
        assert pt.emr == D("0.2700")
        assert pt.emr_ordinary == D("0.12")
        assert pt.emr_pref_stacking == D("0.1500")

    def test_emr_24_bracket(self):
        pt = _find_point(self.result, D("100000"))
        assert pt is not None
        assert pt.emr == D("0.2400")

    def test_ss_torpedo_zero_when_no_ss(self):
        for pt in self.result.points:
            assert pt.emr_ss_torpedo == _ZERO
            assert pt.ss_taxable == _ZERO

    def test_ss_service_not_called_when_benefit_zero(self):
        self.mock_ss.assert_not_called()

    def test_ohio_service_not_called(self):
        self.mock_ohio.assert_not_called()

    def test_component_sums_at_spec_points(self):
        for income in (D("0"), D("6000"), D("30000"), D("100000")):
            pt = _find_point(self.result, income)
            _assert_component_sum(pt)

    def test_boundary_point_stacking_start(self):
        pt = _find_point(self.result, D("27100"))
        assert pt is not None, "Stacking boundary 27100 missing from output"
        assert pt.emr == D("0.2700")


# ---------------------------------------------------------------------------
# Example B — Ordinary Sweep, With SS Torpedo
# Provisional income already in 85% tier. Torpedo active from start,
# exhausted at variable ~10000.
# ---------------------------------------------------------------------------

class TestExampleBSSTorpedo:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=D("15000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("8000"),
            ss_benefit=D("24000"), qualified_dividends=D("3000"),
            fixed_ltcg=D("5000"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("100"), sweep_ceiling=D("90000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_emr_torpedo_at_start(self):
        pt = _find_point(self.result, D("0"))
        assert pt is not None
        # 0.2220: $1000 × 12% + $1000 × 85% × 12% = $120 + $102 = $222 → 22.2%
        assert pt.emr == D("0.2220")
        assert pt.total_tax == D("2090")
        assert pt.ss_taxable == D("12150")
        assert pt.taxable_ordinary == D("19400")

    def test_emr_torpedo_at_5000(self):
        pt = _find_point(self.result, D("5000"))
        assert pt is not None
        assert pt.emr == D("0.2220")
        assert pt.total_tax == D("3200")
        assert pt.ss_taxable == D("16400")

    def test_torpedo_component_at_5000(self):
        pt = _find_point(self.result, D("5000"))
        assert pt.emr_ordinary == D("0.12")
        assert pt.emr_ss_torpedo == D("0.1020")
        assert pt.emr_pref_stacking == _ZERO

    def test_torpedo_exhausted_at_10000(self):
        pt = _find_point(self.result, D("10000"))
        assert pt is not None
        assert pt.emr == D("0.1200")
        assert pt.ss_taxable == D("20400")
        assert pt.emr_ss_torpedo == _ZERO

    def test_torpedo_remains_zero_above_cap(self):
        for pt in self.result.points:
            if pt.income >= D("10000"):
                assert pt.emr_ss_torpedo == _ZERO, (
                    f"Torpedo non-zero at income={pt.income}: {pt.emr_ss_torpedo}"
                )

    def test_emr_stacking_at_15000(self):
        pt = _find_point(self.result, D("15000"))
        assert pt is not None
        assert pt.emr == D("0.2700")
        assert pt.total_tax == D("5225")

    def test_emr_22_bracket(self):
        pt = _find_point(self.result, D("25000"))
        assert pt is not None
        assert pt.emr == D("0.2200")
        assert pt.emr_ordinary == D("0.22")

    def test_emr_24_bracket(self):
        pt = _find_point(self.result, D("80000"))
        assert pt is not None
        assert pt.emr == D("0.2400")
        assert pt.total_tax == D("19884")

    def test_ss_service_called(self):
        assert self.mock_ss.call_count > 0

    def test_component_sums_at_spec_points(self):
        for income in (D("0"), D("5000"), D("10000"), D("25000"), D("80000")):
            pt = _find_point(self.result, income)
            _assert_component_sum(pt)



# ---------------------------------------------------------------------------
# Example C — Preferential Sweep (LTCG Harvesting)
# Ordinary income fixed. Sweep LTCG to find 0%/15% transition at 26350.
# ---------------------------------------------------------------------------

class TestExampleCPreferentialSweep:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=D("20000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("15000"),
            ss_benefit=D("0"), qualified_dividends=D("2000"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            variable_ordinary=D("0"),
            sweep_mode=SweepMode.PREFERENTIAL,
            filing_status="single", tax_year=2025,
            sweep_step=D("100"), sweep_ceiling=D("60000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_result_metadata(self):
        assert self.result.sweep_mode == SweepMode.PREFERENTIAL

    def test_emr_zero_in_0pct_bracket(self):
        for income in (D("0"), D("10000"), D("20000")):
            pt = _find_point(self.result, income)
            assert pt is not None
            assert pt.emr == D("0.0000"), f"Expected 0% at income={income}"
            assert pt.total_tax == D("2072")

    def test_emr_15pct_after_boundary(self):
        pt = _find_point(self.result, D("30000"))
        assert pt is not None
        assert pt.emr == D("0.1500")
        assert pt.total_tax == D("2507")

    def test_boundary_point_27100_present(self):
        pt = _find_point(self.result, D("27100"))
        assert pt is not None, "Boundary point 27100 missing from output"

    def test_boundary_point_27100_emr(self):
        pt = _find_point(self.result, D("27100"))
        assert pt.emr == D("0.1500")
        assert pt.total_tax == D("2072")

    def test_emr_ordinary_zero_in_pref_mode(self):
        for pt in self.result.points:
            assert pt.emr_ordinary == _ZERO, (
                f"emr_ordinary non-zero in PREFERENTIAL mode at "
                f"income={pt.income}: {pt.emr_ordinary}"
            )

    def test_taxable_ordinary_fixed(self):
        for pt in self.result.points:
            assert pt.taxable_ordinary == D("19250")

    def test_component_sums(self):
        for pt in self.result.points:
            _assert_component_sum(pt)


# ---------------------------------------------------------------------------
# Ohio inclusion — include_ohio=True
# ---------------------------------------------------------------------------

class TestIncludeOhioTrue:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO, side_effect=_mock_ohio)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=D("20000"), interest=D("2000"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("1000"), sweep_ceiling=D("50000"),
            include_ohio=True,
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_ohio_service_called(self):
        assert self.mock_ohio.call_count > 0

    def test_emr_ohio_positive_in_275_bracket(self):
        pt = _find_point(self.result, D("30000"))
        assert pt is not None
        assert pt.emr_ohio > _ZERO

    def test_ohio_tax_positive(self):
        pt = _find_point(self.result, D("30000"))
        assert pt.ohio_tax > _ZERO

    def test_ohio_included_in_total_tax(self):
        pt = _find_point(self.result, D("30000"))
        assert pt.total_tax > _ZERO
        assert pt.ohio_tax > _ZERO

    def test_component_sums_at_spec_points(self):
        for income in (D("10000"), D("30000")):
            pt = _find_point(self.result, income)
            _assert_component_sum(pt)



# ---------------------------------------------------------------------------
# Ohio exclusion — include_ohio=False
# ---------------------------------------------------------------------------

class TestIncludeOhioFalse:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=D("20000"), interest=D("2000"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("1000"), sweep_ceiling=D("50000"),
            include_ohio=False,
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_ohio_service_not_called(self):
        self.mock_ohio.assert_not_called()

    def test_emr_ohio_zero_all_points(self):
        for pt in self.result.points:
            assert pt.emr_ohio == _ZERO, (
                f"emr_ohio non-zero at income={pt.income}: {pt.emr_ohio}"
            )

    def test_ohio_tax_zero_all_points(self):
        for pt in self.result.points:
            assert pt.ohio_tax == _ZERO, (
                f"ohio_tax non-zero at income={pt.income}: {pt.ohio_tax}"
            )


# ---------------------------------------------------------------------------
# NIIT trigger — ordinary sweep where AGI exceeds $200,000 threshold
# Lines 207-208: niit_base and round_tax branch exercised.
# ---------------------------------------------------------------------------

class TestNIITTrigger:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO, side_effect=_mock_ohio)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        # fixed_ordinary=50000.  At variable=150000 → agi=210000 (>200k threshold)
        # qualified_dividends=10000 provides the NIIT base.
        self.result = calculate_emr(
            pension=D("50000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("10000"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("1000"),
            sweep_floor=D("140000"), sweep_ceiling=D("170000"),
            include_ohio=True,
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_emr_niit_positive_at_threshold_crossing(self):
        # At variable=140000: agi = 200000, exactly at threshold.
        # Adding step pushes MAGI above 200k, so NIIT kicks in marginally.
        pt = _find_point(self.result, D("140000"))
        assert pt is not None
        assert pt.emr_niit > _ZERO

    def test_emr_niit_zero_when_investment_income_fully_taxed(self):
        # At variable=150000: agi = 210000, excess = 10000 >= investment income (10000).
        # NIIT already fully applied to investment income; more ordinary income
        # doesn't increase NIIT, so marginal NIIT = 0.
        pt = _find_point(self.result, D("150000"))
        assert pt is not None
        assert pt.emr_niit == _ZERO

    def test_ohio_tax_still_computed_with_niit(self):
        pt = _find_point(self.result, D("150000"))
        assert pt.ohio_tax > _ZERO

    def test_component_sums_with_niit(self):
        for income in (D("140000"), D("150000"), D("160000")):
            pt = _find_point(self.result, income)
            _assert_component_sum(pt)


# ---------------------------------------------------------------------------
# SS torpedo boundary insertion in PREFERENTIAL mode
# Lines 452-469: SS tier boundaries appear as exact sweep points.
# ---------------------------------------------------------------------------

class TestSSTorpedoBoundaryInsertionPreferential:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        # base_prov = total_ordinary + fixed_pref + tax_exempt + half_ss
        #           = 10000 + 0 + 0 + 10000 = 20000
        # tier_1 boundary: 25000 - 20000 = 5000
        # tier_2 boundary: 34000 - 20000 = 14000
        # ss_max boundary: 34000 + (17000-4500)/0.85 - 20000 ≈ 28706
        self.result = calculate_emr(
            pension=D("10000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("20000"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            variable_ordinary=D("0"),
            sweep_mode=SweepMode.PREFERENTIAL,
            filing_status="single", tax_year=2025,
            sweep_step=D("1000"),
            sweep_floor=D("0"), sweep_ceiling=D("50000"),
        )
        self.incomes = [pt.income for pt in self.result.points]

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_tier_1_boundary_present(self):
        assert D("5000") in self.incomes, (
            "SS tier-1 boundary 5000 missing from sweep output"
        )

    def test_tier_2_boundary_present(self):
        assert D("14000") in self.incomes, (
            "SS tier-2 boundary 14000 missing from sweep output"
        )

    def test_ss_max_boundary_present(self):
        # max_tier_1 = min(0.50*20000, 0.50*9000) = 4500
        # max_taxable = 0.85*20000 = 17000
        # ss_max_prov = 34000 + (17000-4500)/0.85 = 48705.88…
        # boundary = 48705.88… - 20000 = 28705.88… → round_tax → 28706
        assert D("28706") in self.incomes, (
            "SS max-taxability boundary 28706 missing from sweep output"
        )

    def test_ss_service_called(self):
        assert self.mock_ss.call_count > 0


# ---------------------------------------------------------------------------
# IRMAA thresholds — verify returned as non-empty list of Decimals
# Lines 115-117: _get_irmaa_thresholds exercised and propagated to result.
# ---------------------------------------------------------------------------

class TestIRMAAThresholds:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=D("0"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("10000"), sweep_ceiling=D("10000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_irmaa_thresholds_non_empty(self):
        assert len(self.result.irmaa_thresholds) > 0

    def test_irmaa_thresholds_are_decimals(self):
        for t in self.result.irmaa_thresholds:
            assert isinstance(t, Decimal), f"Expected Decimal, got {type(t)}"

    def test_irmaa_thresholds_positive(self):
        for t in self.result.irmaa_thresholds:
            assert t > _ZERO, f"IRMAA threshold should be positive, got {t}"

    def test_irmaa_thresholds_sorted(self):
        thresholds = self.result.irmaa_thresholds
        assert thresholds == sorted(thresholds)


# ---------------------------------------------------------------------------
# Ohio boundary insertion — zero-rate threshold and MAGI credit threshold
# _compute_ordinary_boundaries must insert exact sweep points at both Ohio
# discontinuities when include_ohio=True.
# ---------------------------------------------------------------------------

class TestOhioBoundaryInsertion:
    """Verify Ohio discontinuity boundary points are present in sweep output."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO, side_effect=_mock_ohio)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        # All fixed income = 0 so ohio_agi_base = 0 and ohio_agi = sweep_value.
        # Zero-rate boundary:  ohio_tax_base = 26050 → ohio_agi = 26050 + 2400 = 28450
        # MAGI credit boundary: ohio_agi - exemption = 100000 → ohio_agi = 101900
        # sweep_step=10000 ensures neither boundary falls on a regular point.
        self.result = calculate_emr(
            pension=D("0"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            ohio_qualifying_retirement_income=D("10000"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("10000"),
            sweep_floor=D("0"), sweep_ceiling=D("150000"),
            include_ohio=True,
        )
        self.incomes = [pt.income for pt in self.result.points]

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_zero_rate_boundary_present(self):
        # ohio_tax_base crosses $26,050 at ohio_agi = 26050 + personal_exemption(2400) = 28450.
        # Without this boundary point the spike can appear at a random $10,000-step interval.
        assert D("28450") in self.incomes, (
            "Ohio zero-rate boundary 28450 missing from sweep output; "
            f"incomes={sorted(self.incomes)}"
        )

    def test_magi_credit_boundary_present(self):
        # Retirement income credit drops from $200 to $0 at ohio_agi - exemption(1900) = 100000,
        # i.e. ohio_agi = 101900.  Without this point the ~200% EMR spike appears at the
        # wrong x-coordinate.
        assert D("101900") in self.incomes, (
            "Ohio MAGI credit boundary 101900 missing from sweep output; "
            f"incomes={sorted(self.incomes)}"
        )

    def test_boundaries_absent_when_ohio_excluded(self):
        # When include_ohio=False the Ohio-specific boundary points must not be inserted
        # (they are unused and would only add sweep overhead).
        result_no_ohio = calculate_emr(
            pension=D("0"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_step=D("10000"),
            sweep_floor=D("0"), sweep_ceiling=D("150000"),
            include_ohio=False,
        )
        incomes_no_ohio = [pt.income for pt in result_no_ohio.points]
        assert D("28450") not in incomes_no_ohio, (
            "Ohio zero-rate boundary 28450 should be absent when include_ohio=False"
        )
        assert D("101900") not in incomes_no_ohio, (
            "Ohio MAGI credit boundary 101900 should be absent when include_ohio=False"
        )


# ---------------------------------------------------------------------------
# above_the_line_adjustments — reduces provisional income → lowers SS taxability
# ---------------------------------------------------------------------------

class TestAboveTheLineAdjustments:
    """HSA-style adjustments reduce agi_excluding_ss and therefore ss_taxable."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        # pension=30000 (ordinary), ss_benefit=20000
        # Without adjustment: agi_excl=30000, prov=30000+10000=40000 → 85% tier
        # With adjustment=10000: agi_excl=20000, prov=20000+10000=30000 → 50% tier
        self.result_no_adj = calculate_emr(
            pension=D("30000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("20000"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_floor=D("0"), sweep_ceiling=D("0"), sweep_step=D("100"),
        )
        self.result_with_adj = calculate_emr(
            pension=D("30000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("20000"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_floor=D("0"), sweep_ceiling=D("0"), sweep_step=D("100"),
            above_the_line_adjustments=D("10000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_adjustment_reduces_ss_taxable(self):
        pt_no = _find_point(self.result_no_adj, D("0"))
        pt_adj = _find_point(self.result_with_adj, D("0"))
        assert pt_adj.ss_taxable < pt_no.ss_taxable

    def test_adjustment_reduces_total_tax(self):
        pt_no = _find_point(self.result_no_adj, D("0"))
        pt_adj = _find_point(self.result_with_adj, D("0"))
        assert pt_adj.total_tax < pt_no.total_tax


# ---------------------------------------------------------------------------
# additional_deductions — reduces taxable_ordinary below standard deduction
# ---------------------------------------------------------------------------

class TestAdditionalDeductions:
    """QBI / excess itemized deductions reduce taxable_ordinary further."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        # pension=20000 → taxable_ordinary = 20000-15750=4250 without extra deduction
        # With additional_deductions=4000: taxable_ordinary = 4250-4000=250
        self.result_no_ded = calculate_emr(
            pension=D("20000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_floor=D("0"), sweep_ceiling=D("0"), sweep_step=D("100"),
        )
        self.result_with_ded = calculate_emr(
            pension=D("20000"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_floor=D("0"), sweep_ceiling=D("0"), sweep_step=D("100"),
            additional_deductions=D("4000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_additional_deduction_reduces_taxable_ordinary(self):
        pt_no = _find_point(self.result_no_ded, D("0"))
        pt_ded = _find_point(self.result_with_ded, D("0"))
        assert pt_ded.taxable_ordinary < pt_no.taxable_ordinary
        # Reduction equals the additional deduction amount
        assert pt_no.taxable_ordinary - pt_ded.taxable_ordinary == D("4000")

    def test_additional_deduction_reduces_total_tax(self):
        pt_no = _find_point(self.result_no_ded, D("0"))
        pt_ded = _find_point(self.result_with_ded, D("0"))
        assert pt_ded.total_tax < pt_no.total_tax


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_unsupported_filing_status(self):
        with pytest.raises(ValueError, match="Unsupported filing status"):
            calculate_emr(
                pension=D("0"), interest=D("0"),
                ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
                ss_benefit=D("0"), qualified_dividends=D("0"),
                fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
                sweep_mode=SweepMode.ORDINARY,
                filing_status="hoh", tax_year=2025,
            )

    def test_unsupported_tax_year(self):
        with pytest.raises(ValueError, match="Unsupported tax year"):
            calculate_emr(
                pension=D("0"), interest=D("0"),
                ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
                ss_benefit=D("0"), qualified_dividends=D("0"),
                fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
                sweep_mode=SweepMode.ORDINARY,
                filing_status="single", tax_year=2099,
            )


# ---------------------------------------------------------------------------
# emr_ordinary attribution — zero in sub-deduction zone, bracket rate above
#
# emr_ordinary is derived from whether ordinary_tax changes between the lo and
# hi snapshots (lo and lo + _EMR_COMPUTE_STEP=1000).  It is 0 when both
# snapshots have the same ordinary tax (fully below the standard deduction),
# and equals the marginal bracket rate when ordinary tax increases.
#
# These tests use fixed_ordinary=0, no SS, no preferential so that the only
# source of emr_ordinary is the sweep variable itself.
# ---------------------------------------------------------------------------

class TestEmrOrdinaryAttribution:
    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_emr_ordinary_zero_below_standard_deduction(self):
        # sweep_ceiling=14000 keeps every point AND its +$1,000 EMR compute step
        # (up to 15,000) below the $15,750 standard deduction.  ordinary_tax is
        # $0 at both snapshots for every point, so emr_ordinary must be 0.
        result = calculate_emr(
            pension=D("0"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_floor=D("0"), sweep_ceiling=D("14000"), sweep_step=D("1000"),
        )
        for pt in result.points:
            assert pt.taxable_ordinary == _ZERO, (
                f"income={pt.income}: taxable_ordinary={pt.taxable_ordinary}, expected 0"
            )
            assert pt.emr_ordinary == _ZERO, (
                f"income={pt.income}: emr_ordinary={pt.emr_ordinary} below std deduction, "
                f"expected 0"
            )

    def test_emr_ordinary_equals_bracket_rate_above_standard_deduction(self):
        # sweep_floor=17000 → taxable_ordinary starts at 1,250 (10% bracket).
        # Sweep crosses the 10%→12% boundary at total_ordinary=27,675
        # (taxable=11,925).  For all points strictly above the deduction, emr_ordinary
        # must match the marginal bracket rate at that sweep point.
        result = calculate_emr(
            pension=D("0"), interest=D("0"),
            ordinary_dividends=D("0"), inherited_ira_rmd=D("0"),
            ss_benefit=D("0"), qualified_dividends=D("0"),
            fixed_ltcg=D("0"), tax_exempt_interest=D("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single", tax_year=2025,
            sweep_floor=D("17000"), sweep_ceiling=D("50000"), sweep_step=D("1000"),
        )
        saw_10pct = saw_12pct = False
        for pt in result.points:
            assert pt.taxable_ordinary > _ZERO, (
                f"income={pt.income}: taxable_ordinary should be positive above deduction"
            )
            if pt.taxable_ordinary <= D("11925"):
                # 10% bracket
                assert pt.emr_ordinary == D("0.10"), (
                    f"income={pt.income}: emr_ordinary={pt.emr_ordinary} in 10% bracket, "
                    f"expected 0.10"
                )
                saw_10pct = True
            elif pt.taxable_ordinary <= D("48475"):
                # 12% bracket
                assert pt.emr_ordinary == D("0.12"), (
                    f"income={pt.income}: emr_ordinary={pt.emr_ordinary} in 12% bracket, "
                    f"expected 0.12"
                )
                saw_12pct = True
        assert saw_10pct, "no points found in 10% bracket — test setup may be wrong"
        assert saw_12pct, "no points found in 12% bracket — test setup may be wrong"
