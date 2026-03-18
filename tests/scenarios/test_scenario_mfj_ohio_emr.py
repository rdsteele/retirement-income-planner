# Scenario: MFJ Ohio EMR — Pension + IRA Withdrawals, 2025
#
# Purpose: Regression anchor for MFJ support across the Ohio tax service and
# EMR pipeline. Verifies that:
#   1. The EMR sweep runs without errors for an MFJ household
#   2. Ohio tax components are non-zero (Ohio is included in the sweep)
#   3. The MFJ personal exemption ($4,300 at $80K AGI tier) is reflected
#      in the Ohio calculation at a representative sweep point
#
# Income setup:
#   Pension:                       $40,000  (fixed ordinary)
#   IRA sweep:                     $0–$150,000 (variable ordinary)
#   Filing status:                 MFJ
#   Tax year:                      2025
#   Ohio included:                 yes
#   Qualifying retirement income:  $40,000 (pension only, no IRA for credit)
#
# At sweep_value = $50,000:
#   total_ordinary = 40,000 + 50,000 = $90,000
#   Ohio AGI = $90,000 (no SS)
#   MFJ exemption = $3,800 (tier: $80,001–$749,999)
#   Ohio tax base = 90,000 − 3,800 = $86,200
#   Ohio bracket tax = 342 + 2.75% × (86,200 − 26,050) = 342 + 1654 = $1,996
#   Retirement credit = $200 (MAGI 86,200 < 100,000; retirement income $40,000 > $8,000)
#   Ohio tax = $1,796

from decimal import Decimal

import pytest

from services.emr import SweepMode, calculate_emr


@pytest.fixture(scope="module")
def result():
    return calculate_emr(
        pension=Decimal("40000"),
        interest=Decimal("0"),
        ordinary_dividends=Decimal("0"),
        ira_distributions=Decimal("0"),
        ss_benefit=Decimal("0"),
        qualified_dividends=Decimal("0"),
        fixed_ltcg=Decimal("0"),
        tax_exempt_interest=Decimal("0"),
        sweep_mode=SweepMode.ORDINARY,
        filing_status="mfj",
        tax_year=2025,
        sweep_floor=Decimal("0"),
        sweep_ceiling=Decimal("150000"),
        sweep_step=Decimal("1000"),
        include_ohio=True,
        ohio_medical_deduction=Decimal("0"),
        ohio_qualifying_retirement_income=Decimal("40000"),
    )


class TestMFJOhioEMRBasics:
    def test_sweep_produces_points(self, result):
        assert len(result.points) > 0

    def test_filing_status_is_mfj(self, result):
        assert result.filing_status == "mfj"

    def test_ohio_tax_components_nonzero(self, result):
        # At least one point must have non-zero Ohio EMR component — Ohio is included
        ohio_nonzero = any(p.emr_ohio > Decimal("0") for p in result.points)
        assert ohio_nonzero, "Expected non-zero Ohio EMR component for at least one sweep point"

    def test_ohio_tax_nonzero_at_high_income(self, result):
        # At $90,000 sweep value (pension $40k + sweep $50k = total $90k ordinary),
        # Ohio tax must be non-zero — income is well above the $26,050 zero bracket
        high_income_points = [p for p in result.points if p.income >= Decimal("50000")]
        assert high_income_points, "Expected sweep points at or above $50,000"
        assert any(p.ohio_tax > Decimal("0") for p in high_income_points)


class TestMFJOhioTaxAtSweepPoint:
    """Spot-check Ohio tax at sweep_value = $50,000 (total ordinary = $90,000)."""

    @pytest.fixture(scope="class")
    def point_at_50k(self, result):
        matches = [p for p in result.points if p.income == Decimal("50000")]
        assert matches, "Expected a sweep point at income = 50000"
        return matches[0]

    def test_ohio_tax_at_50k(self, point_at_50k):
        # Ohio tax = $1,996 before credits − $200 credit = $1,796
        assert point_at_50k.ohio_tax == Decimal("1796")

    def test_ohio_emr_is_positive_at_50k(self, point_at_50k):
        # In the 2.75% bracket, Ohio EMR should be ~0.0275
        assert point_at_50k.emr_ohio > Decimal("0")
