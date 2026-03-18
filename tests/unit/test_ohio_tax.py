"""Unit tests for services/ohio_tax.py.

Test cases derived from the worked examples in specs/ohio_tax.md.
All expected values are hand-verified against the spec.
"""

from decimal import Decimal

import pytest

from services.ohio_tax import calculate_ohio_tax


def dec(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# Example 1 — 2025 income profile proxy
#             IRA + pension qualifying retirement income, 2.75% bracket
# ---------------------------------------------------------------------------

class TestExample1IncomeProfileProxy:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=dec("45370"),
            gross_medical_expenses=dec("6557"),
            qualifying_retirement_income=dec("47089"),
            ss_taxable_federal=dec("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == dec("45370")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == dec("2150")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == dec("3154")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == dec("40066")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == dec("727")

    def test_retirement_income_credit(self):
        assert self.result.retirement_income_credit == dec("200")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == dec("527")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.0116")


# ---------------------------------------------------------------------------
# Example 2 — Clean round numbers, 2.75% bracket
# ---------------------------------------------------------------------------

class TestExample2CleanRoundNumbers:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=dec("60000"),
            gross_medical_expenses=dec("8000"),
            qualifying_retirement_income=dec("50000"),
            ss_taxable_federal=dec("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == dec("60000")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == dec("2150")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == dec("3500")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == dec("54350")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == dec("1120")

    def test_retirement_income_credit(self):
        assert self.result.retirement_income_credit == dec("200")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == dec("920")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.0153")


# ---------------------------------------------------------------------------
# Example 3 — Income below $26,050 threshold, zero tax
#             Credit computed but nonrefundable — ohio_tax floored at zero
# ---------------------------------------------------------------------------

class TestExample3BelowZeroBracket:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=dec("28000"),
            gross_medical_expenses=dec("3000"),
            qualifying_retirement_income=dec("20000"),
            ss_taxable_federal=dec("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == dec("28000")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == dec("2400")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == dec("900")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == dec("24700")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == dec("0")

    def test_retirement_income_credit(self):
        # Credit is $200 even though it cannot be applied — nonrefundable
        assert self.result.retirement_income_credit == dec("200")

    def test_ohio_tax(self):
        # Credit cannot reduce tax below zero
        assert self.result.ohio_tax == dec("0")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.0000")


# ---------------------------------------------------------------------------
# Example 4 — High medical expenses, minimal tax
#             Medical deduction eliminates most taxable income
# ---------------------------------------------------------------------------

class TestExample4HighMedicalExpenses:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=dec("40000"),
            gross_medical_expenses=dec("10000"),
            qualifying_retirement_income=dec("30000"),
            ss_taxable_federal=dec("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == dec("40000")

    def test_personal_exemption(self):
        # AGI exactly at $40,000 boundary → $2,400 tier
        assert self.result.personal_exemption == dec("2400")

    def test_medical_deduction(self):
        assert self.result.medical_deduction == dec("7000")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == dec("30600")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == dec("467")

    def test_retirement_income_credit(self):
        assert self.result.retirement_income_credit == dec("200")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == dec("267")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.0067")


# ---------------------------------------------------------------------------
# Example 5 — Income into 3.125% bracket, credit disqualified
#             MAGI less exemption exceeds $100,000
# ---------------------------------------------------------------------------

class TestExample5HighIncomeNoCreditEligibility:
    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=dec("110000"),
            gross_medical_expenses=dec("5000"),
            qualifying_retirement_income=dec("90000"),
            ss_taxable_federal=dec("0"),
            tax_year=2025,
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == dec("110000")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == dec("1900")

    def test_medical_deduction(self):
        # Medical floor ($8,250) exceeds gross medical ($5,000)
        assert self.result.medical_deduction == dec("0")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == dec("108100")

    def test_tax_before_credits(self):
        assert self.result.tax_before_credits == dec("2647")

    def test_retirement_income_credit(self):
        # MAGI ($110,000) less exemption ($1,900) = $108,100 ≥ $100,000 → disqualified
        assert self.result.retirement_income_credit == dec("0")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == dec("2647")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.0241")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_agi_all_outputs_zero(self):
        result = calculate_ohio_tax(dec("0"), dec("0"), dec("0"), dec("0"), 2025)
        assert result.ohio_agi == dec("0")
        assert result.personal_exemption == dec("2400")
        assert result.medical_deduction == dec("0")
        assert result.ohio_tax_base == dec("0")
        assert result.tax_before_credits == dec("0")
        assert result.retirement_income_credit == dec("0")
        assert result.ohio_tax == dec("0")
        assert result.effective_rate == dec("0")

    def test_zero_medical_expenses_no_deduction(self):
        result = calculate_ohio_tax(dec("50000"), dec("0"), dec("0"), dec("0"), 2025)
        assert result.medical_deduction == dec("0")

    def test_medical_expenses_below_floor_no_deduction(self):
        # Floor = 50000 * 0.075 = 3750; gross = 2000 → deduction = 0
        result = calculate_ohio_tax(dec("50000"), dec("2000"), dec("0"), dec("0"), 2025)
        assert result.medical_deduction == dec("0")

    def test_ss_reduces_ohio_agi(self):
        # Ohio deducts taxable SS from federal AGI
        result = calculate_ohio_tax(dec("50000"), dec("0"), dec("0"), dec("5000"), 2025)
        assert result.ohio_agi == dec("45000")

    def test_qualifying_retirement_income_at_or_below_500_no_credit(self):
        # Tier table: income_up_to "500" → credit $0
        result = calculate_ohio_tax(dec("50000"), dec("0"), dec("500"), dec("0"), 2025)
        assert result.retirement_income_credit == dec("0")

    def test_qualifying_retirement_income_501_credit_25(self):
        result = calculate_ohio_tax(dec("50000"), dec("0"), dec("501"), dec("0"), 2025)
        assert result.retirement_income_credit == dec("25")

    def test_magi_exactly_at_threshold_is_disqualified(self):
        # Threshold check: (ohio_agi - exemption) < 100000
        # ohio_agi = 102150 → exemption = 1900 → magi - exemption = 100250 ≥ 100000 → disqualified
        result = calculate_ohio_tax(dec("102150"), dec("0"), dec("50000"), dec("0"), 2025)
        assert result.retirement_income_credit == dec("0")

    def test_magi_just_below_threshold_is_eligible(self):
        # ohio_agi = 101900 → exemption = 1900 → 100000 - disqualified? No: 101900-1900=100000
        # 100000 < 100000 is False → disqualified
        # ohio_agi = 101899 → 101899-1900=99999 < 100000 → eligible
        result = calculate_ohio_tax(dec("101899"), dec("0"), dec("50000"), dec("0"), 2025)
        assert result.retirement_income_credit == dec("200")

    def test_nonrefundable_credit_cannot_produce_negative_tax(self):
        # tax_before_credits < credit → ohio_tax must be 0, not negative
        # Example 3 already covers this — verify directly
        result = calculate_ohio_tax(dec("28000"), dec("3000"), dec("20000"), dec("0"), 2025)
        assert result.tax_before_credits == dec("0")
        assert result.retirement_income_credit == dec("200")
        assert result.ohio_tax == dec("0")


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
            federal_agi=dec("52150"),
            gross_medical_expenses=dec("0"),
            qualifying_retirement_income=dec("0"),
            ss_taxable_federal=dec("0"),
            tax_year=2026,
        )
        self.result_150k = calculate_ohio_tax(
            federal_agi=dec("151900"),
            gross_medical_expenses=dec("0"),
            qualifying_retirement_income=dec("0"),
            ss_taxable_federal=dec("0"),
            tax_year=2026,
        )

    def test_50k_tax_base(self):
        assert self.result_50k.ohio_tax_base == dec("50000")

    def test_50k_ohio_tax_uses_2026_base(self):
        # 332 + 2.75% × (50,000 − 26,050) = 332 + 658.625 = 990.625 → $991
        assert self.result_50k.ohio_tax == dec("991")

    def test_150k_tax_base(self):
        assert self.result_150k.ohio_tax_base == dec("150000")

    def test_150k_still_275_rate_no_upper_bracket(self):
        # 2026 has no 3.125% bracket — 2.75% applies beyond $26,050 without limit
        # 332 + 2.75% × (150,000 − 26,050) = 332 + 3408.625 = 3740.625 → $3,741
        assert self.result_150k.ohio_tax == dec("3741")

    def test_no_bracket_jump_between_50k_and_150k(self):
        # In 2025 a 3.125% upper bracket caused a rate increase above $100,000.
        # In 2026 the incremental rate across the full range should be a flat 2.75%.
        delta_tax = self.result_150k.ohio_tax - self.result_50k.ohio_tax
        delta_base = self.result_150k.ohio_tax_base - self.result_50k.ohio_tax_base
        assert delta_tax / delta_base == dec("0.0275")

    def test_unsupported_tax_year_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported tax year"):
            calculate_ohio_tax(dec("50000"), dec("0"), dec("0"), dec("0"), 2099)


# ---------------------------------------------------------------------------
# MFJ filing status — personal exemption and retirement income credit
# ---------------------------------------------------------------------------

class TestMFJExemptionTiers:
    """MFJ exemption is the doubled per-person amount stored in personal_exemption_mfj."""

    def test_mfj_tier_40k_or_less(self):
        # AGI = $30,000 → MFJ tier ≤ $40,000 → exemption = $4,800
        result = calculate_ohio_tax(dec("30000"), dec("0"), dec("0"), dec("0"), 2025,
                                    filing_status="mfj")
        assert result.personal_exemption == dec("4800")

    def test_mfj_tier_40k_to_80k(self):
        # AGI = $60,000 → MFJ tier $40,001–$80,000 → exemption = $4,300
        result = calculate_ohio_tax(dec("60000"), dec("0"), dec("0"), dec("0"), 2025,
                                    filing_status="mfj")
        assert result.personal_exemption == dec("4300")

    def test_mfj_tier_80k_to_749k(self):
        # AGI = $90,000 → MFJ tier $80,001–$749,999 → exemption = $3,800
        result = calculate_ohio_tax(dec("90000"), dec("0"), dec("0"), dec("0"), 2025,
                                    filing_status="mfj")
        assert result.personal_exemption == dec("3800")

    def test_mfj_tier_750k_plus(self):
        # AGI = $800,000 → MFJ tier ≥ $750,000 → exemption = $0
        result = calculate_ohio_tax(dec("800000"), dec("0"), dec("0"), dec("0"), 2025,
                                    filing_status="mfj")
        assert result.personal_exemption == dec("0")


class TestMFJRetirementCreditEligibility:
    """MFJ uses combined exemption in the MAGI < $100,000 eligibility check."""

    def test_mfj_credit_eligible_uses_combined_exemption(self):
        # AGI = $103,800 → MFJ exemption = $3,800 → MAGI−exemption = $100,000
        # < $100,000 is False → disqualified
        # AGI = $103,799 → 103,799−3,800 = 99,999 < $100,000 → eligible
        result = calculate_ohio_tax(dec("103799"), dec("0"), dec("50000"), dec("0"), 2025,
                                    filing_status="mfj")
        assert result.retirement_income_credit == dec("200")

    def test_mfj_credit_disqualified_combined_threshold(self):
        # AGI = $103,800 → 103,800−3,800 = 100,000 → NOT < 100,000 → disqualified
        result = calculate_ohio_tax(dec("103800"), dec("0"), dec("50000"), dec("0"), 2025,
                                    filing_status="mfj")
        assert result.retirement_income_credit == dec("0")


class TestMFJWorkedExample:
    """MFJ worked example from spec: pension + IRA withdrawals, tax year 2025."""

    def setup_method(self):
        self.result = calculate_ohio_tax(
            federal_agi=dec("90000"),
            gross_medical_expenses=dec("5000"),
            qualifying_retirement_income=dec("70000"),
            ss_taxable_federal=dec("0"),
            tax_year=2025,
            filing_status="mfj",
        )

    def test_ohio_agi(self):
        assert self.result.ohio_agi == dec("90000")

    def test_personal_exemption(self):
        assert self.result.personal_exemption == dec("3800")

    def test_medical_deduction(self):
        # Medical floor = 90000 × 7.5% = 6750 > 5000 → deduction = 0
        assert self.result.medical_deduction == dec("0")

    def test_ohio_tax_base(self):
        assert self.result.ohio_tax_base == dec("86200")

    def test_tax_before_credits(self):
        # 342.00 + 2.75% × (86200 − 26050) = 342.00 + 1654.125 → $1996
        assert self.result.tax_before_credits == dec("1996")

    def test_retirement_income_credit(self):
        # MAGI less exemption = 86200 < 100000 → eligible; income > 8000 → $200
        assert self.result.retirement_income_credit == dec("200")

    def test_ohio_tax(self):
        assert self.result.ohio_tax == dec("1796")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.0200")


class TestMFJWithSS:
    """MFJ with SS income: ohio_agi = federal_agi - ss_taxable (same as single)."""

    def test_mfj_ss_reduces_ohio_agi(self):
        result = calculate_ohio_tax(dec("70000"), dec("0"), dec("0"), dec("10000"), 2025,
                                    filing_status="mfj")
        assert result.ohio_agi == dec("60000")

    def test_mfj_ss_uses_mfj_exemption_on_reduced_agi(self):
        # ohio_agi = 70000 − 10000 = 60000 → MFJ $40,001–$80,000 tier → $4,300
        result = calculate_ohio_tax(dec("70000"), dec("0"), dec("0"), dec("10000"), 2025,
                                    filing_status="mfj")
        assert result.personal_exemption == dec("4300")


class TestUnsupportedFilingStatus:
    def test_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported filing status"):
            calculate_ohio_tax(dec("50000"), dec("0"), dec("0"), dec("0"), 2025,
                               filing_status="mfs")
