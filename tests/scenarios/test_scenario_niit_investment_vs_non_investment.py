# Scenario Test: NIIT counts investment income only
#
# Single filer, tax year 2026, standard deduction applies.
# Hand-verified: total ordinary income 210,000 - deduction 16,100 = 193,900 taxable.
#   10% x 12,400 = 1,240; 12% x 38,000 = 4,560; 22% x 55,300 = 12,166;
#   24% x 88,200 = 21,168  ->  ordinary tax 39,134.
# MAGI 210,000 exceeds the NIIT threshold by 10,000.
#   - Non-investment income (pension / IRA): NII = 0           -> NIIT 0
#   - 60,000 of investment income: min(60,000, 10,000) x 3.8%  -> NIIT 380
#
# Purpose: regression anchor for the investment / non-investment ordinary split.

from decimal import Decimal

from services.emr import SweepMode, calculate_emr

_ZERO = Decimal("0")


def _total_tax_at_floor(
    *,
    pension: Decimal = _ZERO,
    interest: Decimal = _ZERO,
    ira_distributions: Decimal = _ZERO,
    other_investment_ordinary: Decimal = _ZERO,
) -> Decimal:
    result = calculate_emr(
        pension=pension,
        interest=interest,
        ordinary_dividends=_ZERO,
        ira_distributions=ira_distributions,
        other_investment_ordinary=other_investment_ordinary,
        ss_benefit=_ZERO,
        qualified_dividends=_ZERO,
        fixed_ltcg=_ZERO,
        tax_exempt_interest=_ZERO,
        sweep_mode=SweepMode.ORDINARY,
        filing_status="single",
        tax_year=2026,
        sweep_floor=_ZERO,
        sweep_ceiling=Decimal("100"),
        sweep_step=Decimal("100"),
    )
    return result.points[0].total_tax


class TestNIITInvestmentVersusNonInvestment:
    def test_pension_only_has_no_niit(self):
        assert _total_tax_at_floor(pension=Decimal("210000")) == Decimal("39134")

    def test_ira_only_has_no_niit(self):
        assert _total_tax_at_floor(ira_distributions=Decimal("210000")) == Decimal("39134")

    def test_interest_triggers_niit(self):
        total = _total_tax_at_floor(pension=Decimal("150000"), interest=Decimal("60000"))
        assert total == Decimal("39514")

    def test_other_investment_ordinary_triggers_niit(self):
        total = _total_tax_at_floor(
            pension=Decimal("150000"), other_investment_ordinary=Decimal("60000")
        )
        assert total == Decimal("39514")

    def test_other_investment_ordinary_is_taxed_as_ordinary_income(self):
        without = _total_tax_at_floor(pension=Decimal("150000"))
        with_other = _total_tax_at_floor(
            pension=Decimal("150000"), other_investment_ordinary=Decimal("60000")
        )
        assert with_other > without

    def test_below_threshold_other_investment_has_no_niit(self):
        # 50,000 pension + 40,000 other investment: MAGI 90,000 < threshold
        both = _total_tax_at_floor(
            pension=Decimal("50000"), other_investment_ordinary=Decimal("40000")
        )
        as_pension = _total_tax_at_floor(pension=Decimal("90000"))
        assert both == as_pension
