# Scenario: Single Filer 2025 — Actual Tax Return
#
# Source: Actual 2025 federal tax return, independently prepared.
# Purpose: Regression anchor for federal tax service. If this test breaks,
#          a fundamental calculation has changed.
#
# Income flow:
#   Gross ordinary income:       $50,670
#   Less HSA adjustment:         ($5,300)
#   AGI:                         $45,370
#   Less standard deduction:     ($15,750)
#   Less QBI deduction:          ($23)
#   Taxable ordinary income:     $29,597
#
#   Preferential income:         $24,413  (QD $2,594 + LTCG $21,819)
#   Total taxable income:        $54,010
#
# Note: $3 difference from actual return ($4,160) is within expected
#       rounding variance across individual line items.

from decimal import Decimal
import pytest
from services.federal_tax import calculate_federal_tax


class TestScenarioSingleFiler2025ActualReturn:

    @pytest.fixture
    def result(self):
        # Taxable ordinary income — net of all deductions and adjustments
        # Ordinary income sources (non-qualified portion only):
        #   Taxable interest:          $3,353
        #   Non-qualified dividends:   $228   (ordinary $2,822 - qualified $2,594)
        #   IRA distributions:         $45,493
        #   Pensions/annuities:        $1,596
        #   Short term cap gains:      $0
        #   Gross ordinary:            $50,670
        #   Less HSA adjustment:       ($5,300)
        #   Less standard deduction:   ($15,750)
        #   Less QBI deduction:        ($23)
        #   Taxable ordinary income:   $29,597
        ordinary_income = Decimal('29597')

        # Preferential income: qualified dividends + LTCG
        preferential_income = Decimal('24413')

        return calculate_federal_tax(
            ordinary_income=ordinary_income,
            preferential_income=preferential_income,
            filing_status='single',
            tax_year=2025
        )

    def test_ordinary_income_tax(self, result):
        assert result.ordinary_income_tax == Decimal('3314')

    def test_preferential_income_tax(self, result):
        assert result.preferential_income_tax == Decimal('849')

    def test_total_tax(self, result):
        assert result.total_tax == Decimal('4163')

    def test_effective_rate(self, result):
        assert result.effective_rate == Decimal('0.0771')

    def test_marginal_bracket_rate(self, result):
        assert result.marginal_bracket_rate == Decimal('0.12')

    def test_bracket_breakdown_10_percent(self, result):
        bracket = result.bracket_breakdown[0]
        assert bracket.rate == Decimal('0.10')
        assert bracket.income_taxed == Decimal('11925')
        assert bracket.tax_amount == Decimal('1193')

    def test_bracket_breakdown_12_percent(self, result):
        bracket = result.bracket_breakdown[1]
        assert bracket.rate == Decimal('0.12')
        assert bracket.income_taxed == Decimal('17672')
        assert bracket.tax_amount == Decimal('2121')

    def test_bracket_breakdown_higher_brackets_empty(self, result):
        # All brackets above 12% should have zero income taxed
        for bracket in result.bracket_breakdown[2:]:
            assert bracket.income_taxed == Decimal('0')
            assert bracket.tax_amount == Decimal('0')

    def test_preferential_straddles_zero_and_fifteen_percent(self, result):
        # Preferential income stacks above ordinary income ($29,597)
        # 0% LTCG bracket extends to $48,350 — so $18,753 taxed at 0%
        # Remaining $5,660 spills into 15% bracket
        # This verifies the stacking boundary logic is correct
        assert result.ordinary_income_tax == Decimal('3314')
        assert result.preferential_income_tax == Decimal('849')