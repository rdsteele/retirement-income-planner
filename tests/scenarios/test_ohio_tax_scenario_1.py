# Scenario: Ohio Single Filer 2025 — Actual Income Profile Proxy
#
# Source: Inputs back-calculated from the 2024 Ohio Schedule of Adjustments
# to reproduce the $3,154 medical deduction. 2025 proxy — to be replaced
# with actual 2025 Ohio IT 1040 values once filed.
#
# Purpose: Regression anchor for Ohio tax service. If this breaks, a
# fundamental calculation has changed.
#
# Income flow:
#   Federal AGI:                   $45,370
#   Less SS (fully exempt):        $0
#   Ohio AGI:                      $45,370
#
#   Personal exemption (40k–80k):  $2,150
#   Gross medical expenses:        $6,557
#   Medical floor (7.5% × AGI):   $3,403
#   Medical deduction:             $3,154
#
#   Ohio tax base:                 $40,066
#   Tax (2.75% bracket formula):   $727
#
#   Qualifying retirement income:  $47,089  (IRA $45,493 + pension $1,596)
#   MAGI less exemption:           $43,220  — under $100,000, credit applies
#   Retirement income credit:      $200     (retirement income > $8,000)
#
#   Ohio tax:                      $527

from decimal import Decimal
import pytest
from services.ohio_tax import calculate_ohio_tax


class TestScenarioOhioSingleFiler2025Proxy:

    @pytest.fixture
    def result(self):
        return calculate_ohio_tax(
            federal_agi=Decimal('45370'),
            gross_medical_expenses=Decimal('6557'),
            qualifying_retirement_income=Decimal('47089'),
            ss_taxable_federal=Decimal('0'),
            tax_year=2025,
        )

    def test_ohio_agi(self, result):
        assert result.ohio_agi == Decimal('45370')

    def test_personal_exemption(self, result):
        assert result.personal_exemption == Decimal('2150')

    def test_medical_deduction(self, result):
        # Back-calculated to reproduce 2024 Schedule of Adjustments deduction
        assert result.medical_deduction == Decimal('3154')

    def test_ohio_tax_base(self, result):
        assert result.ohio_tax_base == Decimal('40066')

    def test_tax_before_credits(self, result):
        assert result.tax_before_credits == Decimal('727')

    def test_retirement_income_credit(self, result):
        # Qualifying income $47,089 > $8,000 → maximum $200 credit
        assert result.retirement_income_credit == Decimal('200')

    def test_ohio_tax(self, result):
        assert result.ohio_tax == Decimal('527')

    def test_effective_rate(self, result):
        assert result.effective_rate == Decimal('0.0116')

    def test_credit_eligibility_magi_under_threshold(self, result):
        # Ohio AGI $45,370 − exemption $2,150 = $43,220 — well under $100,000
        # Verifies that the MAGI threshold check passes for this income profile
        assert result.retirement_income_credit > Decimal('0')
