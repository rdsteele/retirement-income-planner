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
from services.emr import (
    EMRResult,
    SweepMode,
    _get_default_sweep_ceiling,
    calculate_emr,
    compute_planning_signals,
)
from services.federal_tax import FederalTaxResult
from services.ohio_tax import OhioTaxResult
from services.social_security import SocialSecurityResult


def dec(s: str) -> Decimal:
    return Decimal(s)


_ZERO = dec("0")
_TWO_PLACES = Decimal("0.01")
_COMPONENT_TOLERANCE = dec("0.003")

_SINGLE_ORDINARY_BRACKETS = [
    (dec("0"), dec("11925"), dec("0.10")),
    (dec("11925"), dec("48475"), dec("0.12")),
    (dec("48475"), dec("103350"), dec("0.22")),
    (dec("103350"), dec("197300"), dec("0.24")),
    (dec("197300"), dec("250525"), dec("0.32")),
    (dec("250525"), dec("626350"), dec("0.35")),
]

_SINGLE_PREF_BRACKETS = [
    (dec("0"), dec("48350"), dec("0.00")),
    (dec("48350"), dec("533400"), dec("0.15")),
]


# ---------------------------------------------------------------------------
# Mock side-effect helpers
# ---------------------------------------------------------------------------


def _round2(amount: Decimal) -> Decimal:
    return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _mock_federal_single(ordinary_income, preferential_income, filing_status, tax_year):
    """Simplified single-filer bracket computation matching 2025 data."""
    ord_tax = _ZERO
    remaining = ordinary_income
    rate = dec("0.10")
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
        ord_tax += round_tax(remaining * dec("0.37"))
        rate = dec("0.37")

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
        pref_tax += round_tax(pref_remaining * dec("0.20"))

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


def _mock_ss_single(ss_benefit, agi_excluding_ss, tax_exempt_interest, filing_status):
    """Simplified single-filer SS taxability matching IRS formula."""
    half_ss = _round2(ss_benefit * dec("0.50"))
    provisional = agi_excluding_ss + tax_exempt_interest + half_ss

    if ss_benefit == _ZERO:
        return SocialSecurityResult(provisional, _ZERO, _ZERO, "none")

    tier_1, tier_2 = dec("25000"), dec("34000")

    if provisional <= tier_1:
        return SocialSecurityResult(provisional, _ZERO, _ZERO, "none")

    if provisional < tier_2:
        amount = _round2(dec("0.50") * (provisional - tier_1))
        cap = _round2(dec("0.50") * ss_benefit)
        taxable = round_tax(min(amount, cap))
        inc = round_rate(taxable / ss_benefit)
        return SocialSecurityResult(provisional, taxable, inc, "fifty_percent")

    tier_1_range = tier_2 - tier_1
    max_tier_1 = min(
        _round2(dec("0.50") * ss_benefit),
        _round2(dec("0.50") * tier_1_range),
    )
    tier_2_amount = _round2(dec("0.85") * (provisional - tier_2))
    max_taxable = _round2(dec("0.85") * ss_benefit)
    taxable = round_tax(min(max_taxable, tier_2_amount + max_tier_1))
    inc = round_rate(taxable / ss_benefit)
    return SocialSecurityResult(provisional, taxable, inc, "eighty_five_percent")


def _mock_ohio(
    federal_agi,
    gross_medical_expenses,
    qualifying_retirement_income,
    ss_taxable_federal,
    tax_year,
    filing_status="single",
):
    """Simplified Ohio tax returning a fixed-rate result for EMR testing."""
    ohio_agi = federal_agi - ss_taxable_federal
    pe = (
        dec("2400")
        if ohio_agi <= dec("40000")
        else (dec("2150") if ohio_agi <= dec("80000") else dec("1900"))
    )

    medical_floor = round_tax(ohio_agi * dec("0.075"))
    med_ded = max(_ZERO, gross_medical_expenses - medical_floor)

    tax_base = max(_ZERO, ohio_agi - pe - med_ded)

    if tax_base <= dec("26050"):
        tax_before = _ZERO
    elif tax_base <= dec("100000"):
        tax_before = dec("342") + round_tax(dec("0.0275") * (tax_base - dec("26050")))
    else:
        tax_before = dec("2394") + round_tax(dec("0.03125") * (tax_base - dec("100000")))

    credit = _ZERO
    if (ohio_agi - pe) < dec("100000") and qualifying_retirement_income > _ZERO:
        if qualifying_retirement_income > dec("8000"):
            credit = dec("200")
        elif qualifying_retirement_income > dec("5000"):
            credit = dec("130")
        elif qualifying_retirement_income > dec("3000"):
            credit = dec("80")
        elif qualifying_retirement_income > dec("1500"):
            credit = dec("50")
        elif qualifying_retirement_income > dec("500"):
            credit = dec("25")

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
    component_sum = (
        pt.emr_ordinary + pt.emr_ss_torpedo + pt.emr_pref_stacking + pt.emr_niit + pt.emr_ohio
    )
    diff = abs(pt.emr - component_sum)
    assert diff <= tolerance, (
        f"At income={pt.income}: emr={pt.emr}, component_sum={component_sum}, diff={diff}"
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
            pension=dec("20000"),
            interest=dec("2000"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("5000"),
            fixed_ltcg=dec("10000"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("100"),
            sweep_ceiling=dec("110000"),
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
        pt = _find_point(self.result, dec("0"))
        assert pt is not None
        assert pt.emr == dec("0.1000")
        assert pt.total_tax == dec("625")
        assert pt.taxable_ordinary == dec("6250")

    def test_emr_in_12_bracket(self):
        pt = _find_point(self.result, dec("6000"))
        assert pt is not None
        assert pt.emr == dec("0.1200")
        assert pt.total_tax == dec("1232")

    def test_emr_stacking_zone(self):
        pt = _find_point(self.result, dec("30000"))
        assert pt is not None
        assert pt.emr == dec("0.2700")
        assert pt.emr_ordinary == dec("0.12")
        assert pt.emr_pref_stacking == dec("0.1500")

    def test_emr_24_bracket(self):
        pt = _find_point(self.result, dec("100000"))
        assert pt is not None
        assert pt.emr == dec("0.2400")

    def test_ss_torpedo_zero_when_no_ss(self):
        for pt in self.result.points:
            assert pt.emr_ss_torpedo == _ZERO
            assert pt.ss_taxable == _ZERO

    def test_ss_service_not_called_when_benefit_zero(self):
        self.mock_ss.assert_not_called()

    def test_ohio_service_not_called(self):
        self.mock_ohio.assert_not_called()

    def test_component_sums_at_spec_points(self):
        for income in (dec("0"), dec("6000"), dec("30000"), dec("100000")):
            pt = _find_point(self.result, income)
            _assert_component_sum(pt)

    def test_boundary_point_stacking_start(self):
        pt = _find_point(self.result, dec("27100"))
        assert pt is not None, "Stacking boundary 27100 missing from output"
        assert pt.emr == dec("0.2700")


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
            pension=dec("15000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("8000"),
            ss_benefit=dec("24000"),
            qualified_dividends=dec("3000"),
            fixed_ltcg=dec("5000"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("100"),
            sweep_ceiling=dec("90000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_emr_torpedo_at_start(self):
        pt = _find_point(self.result, dec("0"))
        assert pt is not None
        # 0.2220: $1000 × 12% + $1000 × 85% × 12% = $120 + $102 = $222 → 22.2%
        assert pt.emr == dec("0.2220")
        assert pt.total_tax == dec("2090")
        assert pt.ss_taxable == dec("12150")
        assert pt.taxable_ordinary == dec("19400")

    def test_emr_torpedo_at_5000(self):
        pt = _find_point(self.result, dec("5000"))
        assert pt is not None
        assert pt.emr == dec("0.2220")
        assert pt.total_tax == dec("3200")
        assert pt.ss_taxable == dec("16400")

    def test_torpedo_component_at_5000(self):
        pt = _find_point(self.result, dec("5000"))
        assert pt.emr_ordinary == dec("0.12")
        assert pt.emr_ss_torpedo == dec("0.1020")
        assert pt.emr_pref_stacking == _ZERO

    def test_torpedo_exhausted_at_10000(self):
        pt = _find_point(self.result, dec("10000"))
        assert pt is not None
        assert pt.emr == dec("0.1200")
        assert pt.ss_taxable == dec("20400")
        assert pt.emr_ss_torpedo == _ZERO

    def test_torpedo_remains_zero_above_cap(self):
        for pt in self.result.points:
            if pt.income >= dec("10000"):
                assert pt.emr_ss_torpedo == _ZERO, (
                    f"Torpedo non-zero at income={pt.income}: {pt.emr_ss_torpedo}"
                )

    def test_emr_stacking_at_15000(self):
        pt = _find_point(self.result, dec("15000"))
        assert pt is not None
        assert pt.emr == dec("0.2700")
        assert pt.total_tax == dec("5225")

    def test_emr_22_bracket(self):
        pt = _find_point(self.result, dec("25000"))
        assert pt is not None
        assert pt.emr == dec("0.2200")
        assert pt.emr_ordinary == dec("0.22")

    def test_emr_24_bracket(self):
        pt = _find_point(self.result, dec("80000"))
        assert pt is not None
        assert pt.emr == dec("0.2400")
        assert pt.total_tax == dec("19884")

    def test_ss_service_called(self):
        assert self.mock_ss.call_count > 0

    def test_component_sums_at_spec_points(self):
        for income in (dec("0"), dec("5000"), dec("10000"), dec("25000"), dec("80000")):
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
            pension=dec("20000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("15000"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("2000"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            variable_ordinary=dec("0"),
            sweep_mode=SweepMode.PREFERENTIAL,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("100"),
            sweep_ceiling=dec("60000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_result_metadata(self):
        assert self.result.sweep_mode == SweepMode.PREFERENTIAL

    def test_emr_zero_in_0pct_bracket(self):
        for income in (dec("0"), dec("10000"), dec("20000")):
            pt = _find_point(self.result, income)
            assert pt is not None
            assert pt.emr == dec("0.0000"), f"Expected 0% at income={income}"
            assert pt.total_tax == dec("2072")

    def test_emr_15pct_after_boundary(self):
        pt = _find_point(self.result, dec("30000"))
        assert pt is not None
        assert pt.emr == dec("0.1500")
        assert pt.total_tax == dec("2507")

    def test_boundary_point_27100_present(self):
        pt = _find_point(self.result, dec("27100"))
        assert pt is not None, "Boundary point 27100 missing from output"

    def test_boundary_point_27100_emr(self):
        pt = _find_point(self.result, dec("27100"))
        assert pt.emr == dec("0.1500")
        assert pt.total_tax == dec("2072")

    def test_emr_ordinary_zero_in_pref_mode(self):
        for pt in self.result.points:
            assert pt.emr_ordinary == _ZERO, (
                f"emr_ordinary non-zero in PREFERENTIAL mode at "
                f"income={pt.income}: {pt.emr_ordinary}"
            )

    def test_taxable_ordinary_fixed(self):
        for pt in self.result.points:
            assert pt.taxable_ordinary == dec("19250")

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
            pension=dec("20000"),
            interest=dec("2000"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("1000"),
            sweep_ceiling=dec("50000"),
            include_ohio=True,
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_ohio_service_called(self):
        assert self.mock_ohio.call_count > 0

    def test_emr_ohio_positive_in_275_bracket(self):
        pt = _find_point(self.result, dec("30000"))
        assert pt is not None
        assert pt.emr_ohio > _ZERO

    def test_ohio_tax_positive(self):
        pt = _find_point(self.result, dec("30000"))
        assert pt.ohio_tax > _ZERO

    def test_ohio_included_in_total_tax(self):
        pt = _find_point(self.result, dec("30000"))
        assert pt.total_tax > _ZERO
        assert pt.ohio_tax > _ZERO

    def test_component_sums_at_spec_points(self):
        for income in (dec("10000"), dec("30000")):
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
            pension=dec("20000"),
            interest=dec("2000"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("1000"),
            sweep_ceiling=dec("50000"),
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
            assert pt.emr_ohio == _ZERO, f"emr_ohio non-zero at income={pt.income}: {pt.emr_ohio}"

    def test_ohio_tax_zero_all_points(self):
        for pt in self.result.points:
            assert pt.ohio_tax == _ZERO, f"ohio_tax non-zero at income={pt.income}: {pt.ohio_tax}"


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
            pension=dec("50000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("10000"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("1000"),
            sweep_floor=dec("140000"),
            sweep_ceiling=dec("170000"),
            include_ohio=True,
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_emr_niit_positive_at_threshold_crossing(self):
        # At variable=140000: agi = 200000, exactly at threshold.
        # Adding step pushes MAGI above 200k, so NIIT kicks in marginally.
        pt = _find_point(self.result, dec("140000"))
        assert pt is not None
        assert pt.emr_niit > _ZERO

    def test_emr_niit_zero_when_investment_income_fully_taxed(self):
        # At variable=150000: agi = 210000, excess = 10000 >= investment income (10000).
        # NIIT already fully applied to investment income; more ordinary income
        # doesn't increase NIIT, so marginal NIIT = 0.
        pt = _find_point(self.result, dec("150000"))
        assert pt is not None
        assert pt.emr_niit == _ZERO

    def test_ohio_tax_still_computed_with_niit(self):
        pt = _find_point(self.result, dec("150000"))
        assert pt.ohio_tax > _ZERO

    def test_component_sums_with_niit(self):
        for income in (dec("140000"), dec("150000"), dec("160000")):
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
            pension=dec("10000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("20000"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            variable_ordinary=dec("0"),
            sweep_mode=SweepMode.PREFERENTIAL,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("1000"),
            sweep_floor=dec("0"),
            sweep_ceiling=dec("50000"),
        )
        self.incomes = [pt.income for pt in self.result.points]

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_tier_1_boundary_present(self):
        assert dec("5000") in self.incomes, "SS tier-1 boundary 5000 missing from sweep output"

    def test_tier_2_boundary_present(self):
        assert dec("14000") in self.incomes, "SS tier-2 boundary 14000 missing from sweep output"

    def test_ss_max_boundary_present(self):
        # max_tier_1 = min(0.50*20000, 0.50*9000) = 4500
        # max_taxable = 0.85*20000 = 17000
        # ss_max_prov = 34000 + (17000-4500)/0.85 = 48705.88…
        # boundary = 48705.88… - 20000 = 28705.88… → round_tax → 28706
        assert dec("28706") in self.incomes, (
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
            pension=dec("0"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("10000"),
            sweep_ceiling=dec("10000"),
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
            pension=dec("0"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            ohio_qualifying_retirement_income=dec("10000"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("10000"),
            sweep_floor=dec("0"),
            sweep_ceiling=dec("150000"),
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
        assert dec("28450") in self.incomes, (
            "Ohio zero-rate boundary 28450 missing from sweep output; "
            f"incomes={sorted(self.incomes)}"
        )

    def test_magi_credit_boundary_present(self):
        # Retirement income credit drops from $200 to $0 at ohio_agi - exemption(1900) = 100000,
        # i.e. ohio_agi = 101900.  Without this point the ~200% EMR spike appears at the
        # wrong x-coordinate.
        assert dec("101900") in self.incomes, (
            "Ohio MAGI credit boundary 101900 missing from sweep output; "
            f"incomes={sorted(self.incomes)}"
        )

    def test_boundaries_absent_when_ohio_excluded(self):
        # When include_ohio=False the Ohio-specific boundary points must not be inserted
        # (they are unused and would only add sweep overhead).
        result_no_ohio = calculate_emr(
            pension=dec("0"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("10000"),
            sweep_floor=dec("0"),
            sweep_ceiling=dec("150000"),
            include_ohio=False,
        )
        incomes_no_ohio = [pt.income for pt in result_no_ohio.points]
        assert dec("28450") not in incomes_no_ohio, (
            "Ohio zero-rate boundary 28450 should be absent when include_ohio=False"
        )
        assert dec("101900") not in incomes_no_ohio, (
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
            pension=dec("30000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("20000"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_floor=dec("0"),
            sweep_ceiling=dec("0"),
            sweep_step=dec("100"),
        )
        self.result_with_adj = calculate_emr(
            pension=dec("30000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("20000"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_floor=dec("0"),
            sweep_ceiling=dec("0"),
            sweep_step=dec("100"),
            above_the_line_adjustments=dec("10000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_adjustment_reduces_ss_taxable(self):
        pt_no = _find_point(self.result_no_adj, dec("0"))
        pt_adj = _find_point(self.result_with_adj, dec("0"))
        assert pt_adj.ss_taxable < pt_no.ss_taxable

    def test_adjustment_reduces_total_tax(self):
        pt_no = _find_point(self.result_no_adj, dec("0"))
        pt_adj = _find_point(self.result_with_adj, dec("0"))
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
            pension=dec("20000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_floor=dec("0"),
            sweep_ceiling=dec("0"),
            sweep_step=dec("100"),
        )
        self.result_with_ded = calculate_emr(
            pension=dec("20000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_floor=dec("0"),
            sweep_ceiling=dec("0"),
            sweep_step=dec("100"),
            additional_deductions=dec("4000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_additional_deduction_reduces_taxable_ordinary(self):
        pt_no = _find_point(self.result_no_ded, dec("0"))
        pt_ded = _find_point(self.result_with_ded, dec("0"))
        assert pt_ded.taxable_ordinary < pt_no.taxable_ordinary
        # Reduction equals the additional deduction amount
        assert pt_no.taxable_ordinary - pt_ded.taxable_ordinary == dec("4000")

    def test_additional_deduction_reduces_total_tax(self):
        pt_no = _find_point(self.result_no_ded, dec("0"))
        pt_ded = _find_point(self.result_with_ded, dec("0"))
        assert pt_ded.total_tax < pt_no.total_tax


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_unsupported_filing_status(self):
        with pytest.raises(ValueError, match="Unsupported filing status"):
            calculate_emr(
                pension=dec("0"),
                interest=dec("0"),
                ordinary_dividends=dec("0"),
                ira_distributions=dec("0"),
                ss_benefit=dec("0"),
                qualified_dividends=dec("0"),
                fixed_ltcg=dec("0"),
                tax_exempt_interest=dec("0"),
                sweep_mode=SweepMode.ORDINARY,
                filing_status="hoh",
                tax_year=2025,
            )

    def test_unsupported_tax_year(self):
        with pytest.raises(ValueError, match="Unsupported tax year"):
            calculate_emr(
                pension=dec("0"),
                interest=dec("0"),
                ordinary_dividends=dec("0"),
                ira_distributions=dec("0"),
                ss_benefit=dec("0"),
                qualified_dividends=dec("0"),
                fixed_ltcg=dec("0"),
                tax_exempt_interest=dec("0"),
                sweep_mode=SweepMode.ORDINARY,
                filing_status="single",
                tax_year=2099,
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
            pension=dec("0"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_floor=dec("0"),
            sweep_ceiling=dec("14000"),
            sweep_step=dec("1000"),
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
            pension=dec("0"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_floor=dec("17000"),
            sweep_ceiling=dec("50000"),
            sweep_step=dec("1000"),
        )
        saw_10pct = saw_12pct = False
        for pt in result.points:
            assert pt.taxable_ordinary > _ZERO, (
                f"income={pt.income}: taxable_ordinary should be positive above deduction"
            )
            if pt.taxable_ordinary <= dec("11925"):
                # 10% bracket
                assert pt.emr_ordinary == dec("0.10"), (
                    f"income={pt.income}: emr_ordinary={pt.emr_ordinary} in 10% bracket, "
                    f"expected 0.10"
                )
                saw_10pct = True
            elif pt.taxable_ordinary <= dec("48475"):
                # 12% bracket
                assert pt.emr_ordinary == dec("0.12"), (
                    f"income={pt.income}: emr_ordinary={pt.emr_ordinary} in 12% bracket, "
                    f"expected 0.12"
                )
                saw_12pct = True
        assert saw_10pct, "no points found in 10% bracket — test setup may be wrong"
        assert saw_12pct, "no points found in 12% bracket — test setup may be wrong"


# ---------------------------------------------------------------------------
# sweep_ceiling=None — uses _get_default_sweep_ceiling (24% bracket top)
# Lines 92-95 (_get_default_sweep_ceiling body) and line 608 exercised.
# ---------------------------------------------------------------------------


class TestSweepCeilingDefault:
    """When sweep_ceiling=None, calculate_emr resolves it via _get_default_sweep_ceiling."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=dec("20000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("10000"),
            sweep_ceiling=None,
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_has_points(self):
        assert len(self.result.points) > 0

    def test_ceiling_uses_24pct_bracket_range(self):
        # 2025 single 24% bracket top = 197,300.  The sweep stops near that ceiling;
        # the last point is the bracket-top boundary (taxable=197,300 → variable=193,050).
        incomes = [pt.income for pt in self.result.points]
        assert max(incomes) > dec("100000")
        assert max(incomes) <= dec("197300")


def test_get_default_sweep_ceiling_missing_bracket():
    """_get_default_sweep_ceiling raises ValueError when no 24% bracket exists."""
    fake_data = {
        "ordinary": {
            "single": [
                {"rate": "0.10", "from": "0", "to": "10000", "excess_over": "0", "base": "0"},
                {
                    "rate": "0.12",
                    "from": "10000",
                    "to": "50000",
                    "excess_over": "10000",
                    "base": "1000",
                },
            ]
        },
        "preferential": {"single": []},
        "standard_deduction": {"single": "15000"},
        "niit_threshold": {"single": "200000"},
        "niit_rate": "0.038",
        "irmaa_thresholds": {"single": []},
    }
    with patch("services.emr.load_federal_data", return_value=fake_data):
        with pytest.raises(ValueError, match="No 24% bracket"):
            _get_default_sweep_ceiling("single", 2025)


# ---------------------------------------------------------------------------
# Preferential sweep with Ohio — exercises _compute_preferential_boundaries
# Ohio branch (lines 539-542) when sweep_mode=PREFERENTIAL and include_ohio=True.
# ---------------------------------------------------------------------------


class TestPreferentialSweepWithOhio:
    """Preferential sweep + include_ohio=True exercises Ohio boundaries in preferential mode."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO, side_effect=_mock_ohio)
        self.mock_fed = self.fed_patcher.start()
        self.mock_ss = self.ss_patcher.start()
        self.mock_ohio = self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=dec("20000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.PREFERENTIAL,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("5000"),
            sweep_ceiling=dec("60000"),
            include_ohio=True,
            ohio_qualifying_retirement_income=dec("5000"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_has_points(self):
        assert len(self.result.points) > 0

    def test_ohio_service_called(self):
        assert self.mock_ohio.call_count > 0

    def test_emr_ohio_positive(self):
        # Ohio tax is positive for any non-trivial income
        assert any(pt.emr_ohio > _ZERO for pt in self.result.points)


# ---------------------------------------------------------------------------
# Planning signals — compute_planning_signals service function
# ---------------------------------------------------------------------------


class TestPlanningSignalsOrdinaryWithLTCG:
    """Ordinary sweep with fixed LTCG — tests ltcg_0pct_remaining and ordinary_runway."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.fed_patcher.start()
        self.ss_patcher.start()
        self.ohio_patcher.start()

        # pension=20000, interest=2000 → fixed_ordinary=22000
        # std_deduction=15750 (2025 single), so taxable_ordinary at floor = 6250
        # qualified_dividends=5000, fixed_ltcg=10000 → ltcg_already_used=15000
        # 0% pref ceiling = 48350 (2025 single)
        # ltcg_0pct_remaining = 48350 - 6250 - 15000 = 27100
        # zero_ordinary_space = max(0, 15750 - 22000 - 0) = 0
        # ordinary_runway = 48350 - 15000 + 15750 - 22000 - 0 = 27100
        self.result = calculate_emr(
            pension=dec("20000"),
            interest=dec("2000"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("5000"),
            fixed_ltcg=dec("10000"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("100"),
            sweep_ceiling=dec("50000"),
        )
        self.signals = compute_planning_signals(
            self.result,
            fixed_ordinary=dec("22000"),
            variable_ordinary=dec("0"),
            qualified_dividends=dec("5000"),
            fixed_ltcg=dec("10000"),
            above_the_line_adjustments=dec("0"),
            additional_deductions=dec("0"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_ltcg_0pct_remaining(self):
        assert self.signals.ltcg_0pct_remaining == dec("27100")

    def test_ltcg_0pct_ordinary_runway(self):
        # No deduction cushion (fixed_ordinary > std_deduction), so runway = remaining
        assert self.signals.ltcg_0pct_ordinary_runway == dec("27100")

    def test_zero_ordinary_space(self):
        assert self.signals.zero_ordinary_space == _ZERO

    def test_torpedo_inactive(self):
        assert self.signals.torpedo_active is False


class TestPlanningSignalsOrdinaryWithDeductionCushion:
    """When fixed_ordinary < std_deduction, runway exceeds remaining."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.fed_patcher.start()
        self.ss_patcher.start()
        self.ohio_patcher.start()

        # pension=5000 → fixed_ordinary=5000
        # std_deduction=15750 → taxable_ordinary at floor = 0
        # qualified_dividends=3000, fixed_ltcg=10000 → ltcg_already_used=13000
        # 0% pref ceiling = 48350
        # ltcg_0pct_remaining = 48350 - 0 - 13000 = 35350
        # zero_ordinary_space = max(0, 15750 - 5000 - 0) = 10750
        # ordinary_runway = 48350 - 13000 + 15750 - 5000 - 0 = 46100
        self.result = calculate_emr(
            pension=dec("5000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("3000"),
            fixed_ltcg=dec("10000"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("100"),
            sweep_ceiling=dec("60000"),
        )
        self.signals = compute_planning_signals(
            self.result,
            fixed_ordinary=dec("5000"),
            variable_ordinary=dec("0"),
            qualified_dividends=dec("3000"),
            fixed_ltcg=dec("10000"),
            above_the_line_adjustments=dec("0"),
            additional_deductions=dec("0"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_ltcg_0pct_remaining(self):
        assert self.signals.ltcg_0pct_remaining == dec("35350")

    def test_ltcg_0pct_ordinary_runway(self):
        assert self.signals.ltcg_0pct_ordinary_runway == dec("46100")

    def test_runway_equals_remaining_plus_deduction_cushion(self):
        assert (
            self.signals.ltcg_0pct_ordinary_runway
            == self.signals.ltcg_0pct_remaining + self.signals.zero_ordinary_space
        )

    def test_zero_ordinary_space(self):
        assert self.signals.zero_ordinary_space == dec("10750")


class TestPlanningSignalsNoLTCG:
    """Ordinary sweep with no LTCG — signals return None."""

    def setup_method(self):
        self.fed_patcher = patch(_PATCH_FED, side_effect=_mock_federal_single)
        self.ss_patcher = patch(_PATCH_SS, side_effect=_mock_ss_single)
        self.ohio_patcher = patch(_PATCH_OHIO)
        self.fed_patcher.start()
        self.ss_patcher.start()
        self.ohio_patcher.start()

        self.result = calculate_emr(
            pension=dec("20000"),
            interest=dec("0"),
            ordinary_dividends=dec("0"),
            ira_distributions=dec("0"),
            ss_benefit=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            tax_exempt_interest=dec("0"),
            sweep_mode=SweepMode.ORDINARY,
            filing_status="single",
            tax_year=2025,
            sweep_step=dec("1000"),
            sweep_ceiling=dec("50000"),
        )
        self.signals = compute_planning_signals(
            self.result,
            fixed_ordinary=dec("20000"),
            variable_ordinary=dec("0"),
            qualified_dividends=dec("0"),
            fixed_ltcg=dec("0"),
            above_the_line_adjustments=dec("0"),
            additional_deductions=dec("0"),
        )

    def teardown_method(self):
        self.fed_patcher.stop()
        self.ss_patcher.stop()
        self.ohio_patcher.stop()

    def test_ltcg_0pct_remaining_none(self):
        assert self.signals.ltcg_0pct_remaining is None

    def test_ltcg_0pct_ordinary_runway_none(self):
        assert self.signals.ltcg_0pct_ordinary_runway is None
