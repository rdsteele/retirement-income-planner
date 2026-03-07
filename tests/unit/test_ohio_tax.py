"""Unit tests for services/ohio_tax.py.

Test cases derived from the worked examples in specs/ohio_tax.md.
All expected values are hand-verified against the spec.
"""

from decimal import Decimal

import pytest

from services.ohio_tax import OhioTaxResult, calculate_ohio_tax


def D(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# Example 1 — 2025 income profile proxy
#             IRA + pension qualifying retirement income, 2.75% bracket
# ---------------------------------------------------------------------------

class TestExample1IncomeProfileProxy:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=D("45370"),
            gross_medical_expenses=D("6557"),
            qualifying_retirement_income=D("47089"),
            ss_taxable_federal=D("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == D("45370")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == D("2150")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == D("3154")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == D("40066")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == D("727")

    def test_retirement_income_credit(self):
        assert self.result.retirement_income_credit == D("200")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == D("527")

    def test_effective_rate(self):
        assert self.result.effective_rate == D("0.0116")


# ---------------------------------------------------------------------------
# Example 2 — Clean round numbers, 2.75% bracket
# ---------------------------------------------------------------------------

class TestExample2CleanRoundNumbers:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=D("60000"),
            gross_medical_expenses=D("8000"),
            qualifying_retirement_income=D("50000"),
            ss_taxable_federal=D("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == D("60000")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == D("2150")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == D("3500")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == D("54350")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == D("1120")

    def test_retirement_income_credit(self):
        assert self.result.retirement_income_credit == D("200")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == D("920")

    def test_effective_rate(self):
        assert self.result.effective_rate == D("0.0153")


# ---------------------------------------------------------------------------
# Example 3 — Income below $26,050 threshold, zero tax
#             Credit computed but nonrefundable — ohio_tax floored at zero
# ---------------------------------------------------------------------------

class TestExample3BelowZeroBracket:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=D("28000"),
            gross_medical_expenses=D("3000"),
            qualifying_retirement_income=D("20000"),
            ss_taxable_federal=D("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == D("28000")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == D("2400")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == D("900")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == D("24700")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == D("0")

    def test_retirement_income_credit(self):
        # Credit is $200 even though it cannot be applied — nonrefundable
        assert self.result.retirement_income_credit == D("200")

    def test_ohio_tax(self):
        # Credit cannot reduce tax below zero
        assert self.result.ohio_tax == D("0")

    def test_effective_rate(self):
        assert self.result.effective_rate == D("0.0000")


# ---------------------------------------------------------------------------
# Example 4 — High medical expenses, minimal tax
#             Medical deduction eliminates most taxable income
# ---------------------------------------------------------------------------

class TestExample4HighMedicalExpenses:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=D("40000"),
            gross_medical_expenses=D("10000"),
            qualifying_retirement_income=D("30000"),
            ss_taxable_federal=D("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == D("40000")

    def test_personal_exemption(self):
        # AGI exactly at $40,000 boundary → $2,400 tier
        assert self.result.personal_exemption == D("2400")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == D("7000")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == D("30600")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == D("467")

    def test_retirement_income_credit(self):
        assert self.result.retirement_income_credit == D("200")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == D("267")

    def test_effective_rate(self):
        assert self.result.effective_rate == D("0.0067")


# ---------------------------------------------------------------------------
# Example 5 — Income into 3.125% bracket, credit disqualified
#             MAGI less exemption exceeds $100,000
# ---------------------------------------------------------------------------

class TestExample5HighIncomeNoCreditEligibility:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=D("110000"),
            gross_medical_expenses=D("5000"),
            qualifying_retirement_income=D("90000"),
            ss_taxable_federal=D("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == D("110000")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == D("1900")

    def test_medical_deduction(self):
        # Medical floor ($8,250) exceeds gross medical ($5,000)
        assert self.result.medical_deduction == D("0")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == D("108100")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == D("2647")

    def test_retirement_income_credit(self):
        # MAGI ($110,000) less exemption ($1,900) = $108,100 ≥ $100,000 → disqualified
        assert self.result.retirement_income_credit == D("0")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == D("2647")

    def test_effective_rate(self):
        assert self.result.effective_rate == D("0.0241")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_agi_all_outputs_zero(self):
        result = calculate_ohio_tax(D("0"), D("0"), D("0"), D("0"), 2025)
        assert result.ohio_agi == D("0")
        assert result.personal_exemption == D("2400")
        assert result.medical_deduction == D("0")
        assert result.ohio_tax_base == D("0")
        assert result.tax_before_credits == D("0")
        assert result.retirement_income_credit == D("0")
        assert result.ohio_tax == D("0")
        assert result.effective_rate == D("0")

    def test_zero_medical_expenses_no_deduction(self):
        result = calculate_ohio_tax(D("50000"), D("0"), D("0"), D("0"), 2025)
        assert result.medical_deduction == D("0")

    def test_medical_expenses_below_floor_no_deduction(self):
        # Floor = 50000 * 0.075 = 3750; gross = 2000 → deduction = 0
        result = calculate_ohio_tax(D("50000"), D("2000"), D("0"), D("0"), 2025)
        assert result.medical_deduction == D("0")

    def test_ss_reduces_ohio_agi(self):
        # Ohio deducts taxable SS from federal AGI
        result = calculate_ohio_tax(D("50000"), D("0"), D("0"), D("5000"), 2025)
        assert result.ohio_agi == D("45000")

    def test_qualifying_retirement_income_at_or_below_500_no_credit(self):
        # Tier table: income_up_to "500" → credit $0
        result = calculate_ohio_tax(D("50000"), D("0"), D("500"), D("0"), 2025)
        assert result.retirement_income_credit == D("0")

    def test_qualifying_retirement_income_501_credit_25(self):
        result = calculate_ohio_tax(D("50000"), D("0"), D("501"), D("0"), 2025)
        assert result.retirement_income_credit == D("25")

    def test_magi_exactly_at_threshold_is_disqualified(self):
        # Threshold check: (ohio_agi - exemption) < 100000
        # ohio_agi = 102150 → exemption = 1900 → magi - exemption = 100250 ≥ 100000 → disqualified
        result = calculate_ohio_tax(D("102150"), D("0"), D("50000"), D("0"), 2025)
        assert result.retirement_income_credit == D("0")

    def test_magi_just_below_threshold_is_eligible(self):
        # ohio_agi = 101900 → exemption = 1900 → 100000 - disqualified? No: 101900-1900=100000
        # 100000 < 100000 is False → disqualified
        # ohio_agi = 101899 → 101899-1900=99999 < 100000 → eligible
        result = calculate_ohio_tax(D("101899"), D("0"), D("50000"), D("0"), 2025)
        assert result.retirement_income_credit == D("200")

    def test_nonrefundable_credit_cannot_produce_negative_tax(self):
        # tax_before_credits < credit → ohio_tax must be 0, not negative
        # Example 3 already covers this — verify directly
        result = calculate_ohio_tax(D("28000"), D("3000"), D("20000"), D("0"), 2025)
        assert result.tax_before_credits == D("0")
        assert result.retirement_income_credit == D("200")
        assert result.ohio_tax == D("0")


# ---------------------------------------------------------------------------
# Ohio 2026 — flat 2.75% rate, base changes from $342 to $332 (HB96)
# ---------------------------------------------------------------------------
#
# Setup: no medical expenses, no qualifying retirement income.
# federal_agi=52150 → ohio_agi=52150 → exemption=$2,150 (40K < agi ≤ 80K)
#   → ohio_tax_base = 52,150 − 2,150 = 50,000
# federal_agi=151900 → ohio_agi=151900 → exemption=$1,900 (agi > 80K)
#   → ohio_tax_base = 151,900 − 1,900 = 150,000

class TestOhio2026FlatRate:
    def setup_method(self):
        self.result_50k = calculate_ohio_tax(
            federal_agi=D("52150"),
            gross_medical_expenses=D("0"),
            qualifying_retirement_income=D("0"),
            ss_taxable_federal=D("0"),
            tax_year=2026,
        )
        self.result_150k = calculate_ohio_tax(
            federal_agi=D("151900"),
            gross_medical_expenses=D("0"),
            qualifying_retirement_income=D("0"),
            ss_taxable_federal=D("0"),
            tax_year=2026,
        )

    def test_50k_tax_base(self):
        assert self.result_50k.ohio_tax_base == D("50000")

    def test_50k_ohio_tax_uses_2026_base(self):
        # 332 + 2.75% × (50,000 − 26,050) = 332 + 658.625 = 990.625 → $991
        assert self.result_50k.ohio_tax == D("991")

    def test_150k_tax_base(self):
        assert self.result_150k.ohio_tax_base == D("150000")

    def test_150k_still_275_rate_no_upper_bracket(self):
        # 2026 has no 3.125% bracket — 2.75% applies beyond $26,050 without limit
        # 332 + 2.75% × (150,000 − 26,050) = 332 + 3408.625 = 3740.625 → $3,741
        assert self.result_150k.ohio_tax == D("3741")

    def test_no_bracket_jump_between_50k_and_150k(self):
        # In 2025 a 3.125% upper bracket caused a rate increase above $100,000.
        # In 2026 the incremental rate across the full range should be a flat 2.75%.
        delta_tax = self.result_150k.ohio_tax - self.result_50k.ohio_tax
        delta_base = self.result_150k.ohio_tax_base - self.result_50k.ohio_tax_base
        assert delta_tax / delta_base == D("0.0275")

    def test_unsupported_tax_year_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported tax year"):
            calculate_ohio_tax(D("50000"), D("0"), D("0"), D("0"), 2099)
