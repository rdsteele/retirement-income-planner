"""Unit tests for services/aca.py.

Tests verify the ACA 400% FPL hard cliff behavior: subsidy amount, subsidy loss,
cliff proximity, and marginal subsidy loss at/around the cliff.

Filing status: single unless noted.  Tax year: 2026.
2026 cliff: 15650 × 4 = $62,600 (single), $128,600 (MFJ).
"""

from decimal import Decimal

import pytest

from services.aca import calculate_aca_subsidy


def dec(s: str) -> Decimal:
    return Decimal(s)


CLIFF_SINGLE = dec("62600")
CLIFF_MFJ = dec("128600")
KNOWN_APTC = dec("6240")
SLCSP = dec("10000")   # clean round number for formula tests
TAX_YEAR = 2026


# ---------------------------------------------------------------------------
# 1. Below cliff — correct APTC, zero subsidy loss, positive distance
# ---------------------------------------------------------------------------

class TestBelowCliff:
    def setup_method(self):
        self.result = calculate_aca_subsidy(
            magi=dec("50000"),
            slcsp_annual_premium=SLCSP,
            filing_status="single",
            tax_year=TAX_YEAR,
            known_aptc_annual=KNOWN_APTC,
        )

    def test_is_eligible(self):
        assert self.result.is_eligible is True

    def test_aptc_annual_uses_known_aptc(self):
        assert self.result.aptc_annual == KNOWN_APTC

    def test_aptc_monthly(self):
        assert self.result.aptc_monthly == dec("520")

    def test_subsidy_loss_zero(self):
        assert self.result.subsidy_loss == dec("0")

    def test_distance_to_cliff_positive(self):
        assert self.result.distance_to_cliff == dec("12600")

    def test_marginal_subsidy_loss_zero(self):
        # Below cliff — no marginal loss until cliff is crossed
        assert self.result.marginal_subsidy_loss == dec("0")


# ---------------------------------------------------------------------------
# 2. At exact cliff MAGI — correct APTC, zero subsidy loss, distance=0
# ---------------------------------------------------------------------------

class TestAtExactCliff:
    def setup_method(self):
        self.result = calculate_aca_subsidy(
            magi=CLIFF_SINGLE,
            slcsp_annual_premium=SLCSP,
            filing_status="single",
            tax_year=TAX_YEAR,
            known_aptc_annual=KNOWN_APTC,
        )

    def test_is_eligible(self):
        # 400% FPL = cliff; household is still eligible at exactly the cliff
        assert self.result.is_eligible is True

    def test_aptc_annual(self):
        assert self.result.aptc_annual == KNOWN_APTC

    def test_subsidy_loss_zero(self):
        assert self.result.subsidy_loss == dec("0")

    def test_distance_to_cliff_zero(self):
        assert self.result.distance_to_cliff == dec("0")

    def test_marginal_subsidy_loss_equals_aptc(self):
        # At the cliff, adding $1 more loses the entire APTC
        assert self.result.marginal_subsidy_loss == KNOWN_APTC


# ---------------------------------------------------------------------------
# 3. One dollar over cliff — zero APTC, full subsidy loss, distance=-1
# ---------------------------------------------------------------------------

class TestOneDollarOverCliff:
    def setup_method(self):
        self.result = calculate_aca_subsidy(
            magi=CLIFF_SINGLE + dec("1"),
            slcsp_annual_premium=SLCSP,
            filing_status="single",
            tax_year=TAX_YEAR,
            known_aptc_annual=KNOWN_APTC,
        )

    def test_not_eligible(self):
        assert self.result.is_eligible is False

    def test_aptc_annual_zero(self):
        assert self.result.aptc_annual == dec("0")

    def test_aptc_monthly_zero(self):
        assert self.result.aptc_monthly == dec("0")

    def test_subsidy_loss_full(self):
        assert self.result.subsidy_loss == KNOWN_APTC

    def test_distance_negative_one(self):
        assert self.result.distance_to_cliff == dec("-1")

    def test_marginal_subsidy_loss_zero(self):
        # Already over — no further marginal loss
        assert self.result.marginal_subsidy_loss == dec("0")


# ---------------------------------------------------------------------------
# 4. known_aptc_annual override used when provided
# ---------------------------------------------------------------------------

class TestKnownAptcOverride:
    def test_override_differs_from_formula(self):
        # Formula result at magi=50000, slcsp=10000:
        # required = round_tax(50000 × 0.0996) = 4980
        # formula_aptc = max(0, 10000 - 4980) = 5020
        formula_result = calculate_aca_subsidy(
            magi=dec("50000"),
            slcsp_annual_premium=SLCSP,
            filing_status="single",
            tax_year=TAX_YEAR,
        )
        override_result = calculate_aca_subsidy(
            magi=dec("50000"),
            slcsp_annual_premium=SLCSP,
            filing_status="single",
            tax_year=TAX_YEAR,
            known_aptc_annual=dec("8000"),
        )
        assert formula_result.aptc_annual == dec("5020")
        assert override_result.aptc_annual == dec("8000")

    def test_override_does_not_affect_over_cliff(self):
        # When over cliff, aptc=0 regardless of known_aptc value
        result = calculate_aca_subsidy(
            magi=CLIFF_SINGLE + dec("1"),
            slcsp_annual_premium=SLCSP,
            filing_status="single",
            tax_year=TAX_YEAR,
            known_aptc_annual=dec("8000"),
        )
        assert result.aptc_annual == dec("0")
        assert result.subsidy_loss == dec("8000")


# ---------------------------------------------------------------------------
# 5. Distance to cliff calculation accuracy at various MAGIs
# ---------------------------------------------------------------------------

class TestDistanceAccuracy:
    def test_well_below_cliff(self):
        result = calculate_aca_subsidy(
            magi=dec("40000"), slcsp_annual_premium=SLCSP,
            filing_status="single", tax_year=TAX_YEAR,
        )
        assert result.distance_to_cliff == dec("22600")

    def test_near_cliff(self):
        result = calculate_aca_subsidy(
            magi=dec("62500"), slcsp_annual_premium=SLCSP,
            filing_status="single", tax_year=TAX_YEAR,
        )
        assert result.distance_to_cliff == dec("100")

    def test_one_over_cliff(self):
        result = calculate_aca_subsidy(
            magi=CLIFF_SINGLE + dec("1"), slcsp_annual_premium=SLCSP,
            filing_status="single", tax_year=TAX_YEAR,
        )
        assert result.distance_to_cliff == dec("-1")

    def test_far_over_cliff(self):
        result = calculate_aca_subsidy(
            magi=dec("80000"), slcsp_annual_premium=SLCSP,
            filing_status="single", tax_year=TAX_YEAR,
        )
        assert result.distance_to_cliff == dec("-17400")

    def test_cliff_magi_is_correct(self):
        result = calculate_aca_subsidy(
            magi=dec("50000"), slcsp_annual_premium=SLCSP,
            filing_status="single", tax_year=TAX_YEAR,
        )
        assert result.cliff_magi == CLIFF_SINGLE


# ---------------------------------------------------------------------------
# 6. MFJ cliff uses correct threshold ($128,600)
# ---------------------------------------------------------------------------

class TestMFJCliff:
    def setup_method(self):
        self.result = calculate_aca_subsidy(
            magi=dec("120000"),
            slcsp_annual_premium=dec("15000"),
            filing_status="mfj",
            tax_year=TAX_YEAR,
            known_aptc_annual=dec("10000"),
        )

    def test_cliff_is_mfj_threshold(self):
        assert self.result.cliff_magi == CLIFF_MFJ

    def test_is_eligible_below_mfj_cliff(self):
        assert self.result.is_eligible is True

    def test_distance_to_mfj_cliff(self):
        assert self.result.distance_to_cliff == dec("8600")

    def test_mfj_over_cliff(self):
        result = calculate_aca_subsidy(
            magi=CLIFF_MFJ + dec("1"),
            slcsp_annual_premium=dec("15000"),
            filing_status="mfj",
            tax_year=TAX_YEAR,
            known_aptc_annual=dec("10000"),
        )
        assert result.is_eligible is False
        assert result.aptc_annual == dec("0")
        assert result.distance_to_cliff == dec("-1")


# ---------------------------------------------------------------------------
# Worked example — 2026 single filer near cliff
#   MAGI $62,072 | SLCSP $5,617.08/year | known_aptc $6,240/year
# ---------------------------------------------------------------------------

class TestWorkedExample:
    def setup_method(self):
        self.result = calculate_aca_subsidy(
            magi=dec("62072"),
            slcsp_annual_premium=dec("5617.08"),
            filing_status="single",
            tax_year=2026,
            known_aptc_annual=dec("6240"),
        )

    def test_aptc_annual(self):
        assert self.result.aptc_annual == dec("6240")

    def test_aptc_monthly(self):
        assert self.result.aptc_monthly == dec("520")

    def test_distance_to_cliff(self):
        assert self.result.distance_to_cliff == dec("528")

    def test_is_eligible(self):
        assert self.result.is_eligible is True

    def test_subsidy_loss_zero(self):
        assert self.result.subsidy_loss == dec("0")

    def test_marginal_subsidy_loss_zero(self):
        # $528 below cliff — no marginal loss yet
        assert self.result.marginal_subsidy_loss == dec("0")


# ---------------------------------------------------------------------------
# Error handling — unsupported tax year and invalid filing status
# ---------------------------------------------------------------------------

def test_unsupported_tax_year_raises():
    with pytest.raises(ValueError, match="Unsupported tax year"):
        calculate_aca_subsidy(
            magi=dec("50000"),
            slcsp_annual_premium=dec("10000"),
            filing_status="single",
            tax_year=2099,
        )


def test_invalid_filing_status_raises():
    with pytest.raises(ValueError, match="Unsupported filing status"):
        calculate_aca_subsidy(
            magi=dec("50000"),
            slcsp_annual_premium=dec("10000"),
            filing_status="mfs",
            tax_year=TAX_YEAR,
        )
