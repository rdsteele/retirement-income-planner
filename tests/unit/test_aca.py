"""Unit tests for services/aca.py — schedule-based APTC calculation.

2026 single filer: cliff = $15,650 × 4 = $62,600.
Schedule minimum: $22,000 (Medicaid boundary).
MFJ cliff: $32,150 × 4 = $128,600 (empty schedule → formula fallback).

Tests:
 1. Schedule interpolation between two points
 2. Schedule exact match on a schedule point
 3. Below lowest schedule point → zero APTC, is_eligible=False
 4. At cliff → aptc=0, last non-zero APTC as marginal spike, distance=0
 5. One dollar over cliff → zero APTC, full subsidy_loss, marginal=0
 6. Subsidy loss correct vs non-default baseline MAGI
 7. Marginal subsidy loss correct between schedule points (gradual slope)
 8. Marginal subsidy loss spikes at cliff crossing
 9. Empty schedule (MFJ) falls back to formula calculation
10. MFJ cliff uses correct threshold ($128,600)
"""

from decimal import Decimal

import pytest

from services.aca import calculate_aca_subsidy

D = Decimal

CLIFF_SINGLE = D("62600")
CLIFF_MFJ    = D("128600")
TAX_YEAR     = 2026


# ---------------------------------------------------------------------------
# 1. Schedule interpolation between two points
#    Spec worked example: MAGI $35,346 between (35000, 820) and (40000, 751)
# ---------------------------------------------------------------------------

class TestScheduleInterpolation:
    """MAGI between two schedule points → linearly interpolated annual APTC."""

    def setup_method(self):
        # fraction = (35346-35000)/(40000-35000) = 346/5000 = 0.0692
        # monthly = 820 + 0.0692×(751-820) = 815.2252
        # annual  = round_tax(815.2252 × 12) = 9783
        self.result = calculate_aca_subsidy(
            magi=D("35346"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )

    def test_is_eligible(self):
        assert self.result.is_eligible is True

    def test_aptc_annual_interpolated(self):
        assert self.result.aptc_annual == D("9783")

    def test_aptc_monthly_derived(self):
        # round_tax(9783 / 12) = round_tax(815.25) = 815
        assert self.result.aptc_monthly == D("815")

    def test_distance_to_cliff_positive(self):
        assert self.result.distance_to_cliff == D("27254")  # 62600 - 35346

    def test_cliff_magi_correct(self):
        assert self.result.cliff_magi == CLIFF_SINGLE


# ---------------------------------------------------------------------------
# 2. Schedule exact match on a schedule point
# ---------------------------------------------------------------------------

class TestScheduleExactMatch:
    """MAGI exactly on a schedule point → uses that point's value directly."""

    def setup_method(self):
        # Schedule: {magi: 35000, monthly_aptc: 820}
        self.result = calculate_aca_subsidy(
            magi=D("35000"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )

    def test_is_eligible(self):
        assert self.result.is_eligible is True

    def test_aptc_annual_exact(self):
        # 820 × 12 = 9840
        assert self.result.aptc_annual == D("9840")

    def test_aptc_monthly_exact(self):
        assert self.result.aptc_monthly == D("820")


# ---------------------------------------------------------------------------
# 3. Below lowest schedule point → zero APTC, is_eligible=False (Medicaid)
# ---------------------------------------------------------------------------

class TestBelowScheduleMinimum:
    """MAGI below $22,000 (Medicaid territory) → ineligible, no APTC."""

    def setup_method(self):
        self.result = calculate_aca_subsidy(
            magi=D("20000"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )

    def test_is_eligible_false(self):
        assert self.result.is_eligible is False

    def test_aptc_annual_zero(self):
        assert self.result.aptc_annual == D("0")

    def test_aptc_monthly_zero(self):
        assert self.result.aptc_monthly == D("0")

    def test_marginal_zero(self):
        assert self.result.marginal_subsidy_loss == D("0")


# ---------------------------------------------------------------------------
# 4. At cliff MAGI → aptc=0, is_eligible=False, distance=0, marginal=spike
# ---------------------------------------------------------------------------

class TestAtCliff:
    """At exactly cliff MAGI: aptc drops to zero; marginal = full last APTC."""

    def setup_method(self):
        # Cliff at 62600; last non-zero schedule point: {62500, 520} → 6240/yr
        self.result = calculate_aca_subsidy(
            magi=CLIFF_SINGLE,
            filing_status="single",
            tax_year=TAX_YEAR,
        )

    def test_is_eligible_false(self):
        assert self.result.is_eligible is False

    def test_aptc_annual_zero(self):
        assert self.result.aptc_annual == D("0")

    def test_distance_to_cliff_zero(self):
        assert self.result.distance_to_cliff == D("0")

    def test_marginal_equals_last_nonzero_aptc(self):
        # Last non-zero monthly = 520 → annual = 6240 (the cliff spike)
        assert self.result.marginal_subsidy_loss == D("6240")


# ---------------------------------------------------------------------------
# 5. One dollar over cliff → zero APTC, full subsidy_loss, marginal=0
# ---------------------------------------------------------------------------

class TestOneDollarOverCliff:
    """Crossing the cliff by $1 loses the full baseline APTC."""

    def setup_method(self):
        # Default baseline = schedule min (22000): 972×12 = 11664
        self.result = calculate_aca_subsidy(
            magi=CLIFF_SINGLE + D("1"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )

    def test_is_eligible_false(self):
        assert self.result.is_eligible is False

    def test_aptc_annual_zero(self):
        assert self.result.aptc_annual == D("0")

    def test_distance_negative_one(self):
        assert self.result.distance_to_cliff == D("-1")

    def test_subsidy_loss_full_baseline(self):
        # Baseline = schedule min MAGI 22000: monthly 972 → annual 11664
        assert self.result.subsidy_loss == D("11664")

    def test_marginal_zero(self):
        # Already over cliff — no further marginal loss
        assert self.result.marginal_subsidy_loss == D("0")


# ---------------------------------------------------------------------------
# 6. Subsidy loss correct vs non-default baseline MAGI
# ---------------------------------------------------------------------------

class TestSubsidyLossVsBaseline:
    """subsidy_loss = max(0, baseline_aptc - current_aptc)."""

    def test_loss_relative_to_explicit_baseline(self):
        # baseline MAGI 25000: monthly 941 → annual 11292
        # current MAGI 35346: annual 9783 (from test 1 worked example)
        result = calculate_aca_subsidy(
            magi=D("35346"),
            filing_status="single",
            tax_year=TAX_YEAR,
            baseline_magi=D("25000"),
        )
        assert result.subsidy_loss == D("1509")  # 11292 - 9783

    def test_loss_zero_at_baseline(self):
        # When current MAGI == baseline_magi, subsidy_loss = 0
        result = calculate_aca_subsidy(
            magi=D("35000"),
            filing_status="single",
            tax_year=TAX_YEAR,
            baseline_magi=D("35000"),
        )
        assert result.subsidy_loss == D("0")


# ---------------------------------------------------------------------------
# 7. Marginal subsidy loss correct between schedule points (gradual slope)
# ---------------------------------------------------------------------------

class TestGradualSlope:
    """Below cliff, slope = (lower - upper) annual / (upper - lower) MAGI × 1000."""

    def test_slope_between_25k_and_30k(self):
        # lower=(25000, 941), upper=(30000, 883)
        # slope = (11292 - 10596) / 5000 × 1000 = 696/5 = 139.2
        result = calculate_aca_subsidy(
            magi=D("27500"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )
        assert result.marginal_subsidy_loss == D("139.2")

    def test_slope_between_50k_and_55k(self):
        # lower=(50000, 623), upper=(55000, 582)
        # slope = (7476 - 6984) / 5000 × 1000 = 492/5 = 98.4
        result = calculate_aca_subsidy(
            magi=D("52000"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )
        assert result.marginal_subsidy_loss == D("98.4")

    def test_last_interval_before_cliff_is_zero(self):
        # Between (62500, 520) and (62600, 0): upper is the cliff point.
        # This interval is treated as the cliff boundary, not a gradual slope.
        result = calculate_aca_subsidy(
            magi=D("62550"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )
        assert result.marginal_subsidy_loss == D("0")


# ---------------------------------------------------------------------------
# 8. Marginal subsidy loss spikes at cliff crossing
# ---------------------------------------------------------------------------

def test_marginal_spike_at_cliff():
    """At the cliff MAGI, marginal_subsidy_loss = last non-zero annual APTC."""
    result = calculate_aca_subsidy(
        magi=CLIFF_SINGLE,
        filing_status="single",
        tax_year=TAX_YEAR,
    )
    # Last non-zero schedule point: {62500, 520} → 520×12 = 6240
    assert result.marginal_subsidy_loss == D("6240")


# ---------------------------------------------------------------------------
# 9. Empty schedule (MFJ) falls back to applicable-percentage formula
# ---------------------------------------------------------------------------

def test_empty_schedule_formula_fallback():
    """MFJ has an empty aptc_schedule; formula uses applicable_percentage_400pct."""
    # required = round_tax(50000 × 0.0996) = 4980
    # aptc     = max(0, 10000 - 4980) = 5020
    result = calculate_aca_subsidy(
        magi=D("50000"),
        filing_status="mfj",
        tax_year=TAX_YEAR,
        slcsp_annual_premium=D("10000"),
    )
    assert result.aptc_annual == D("5020")
    assert result.is_eligible is True
    assert result.cliff_magi == CLIFF_MFJ


# ---------------------------------------------------------------------------
# 10. MFJ cliff uses correct threshold ($128,600)
# ---------------------------------------------------------------------------

class TestMFJCliff:
    def test_cliff_is_mfj_threshold(self):
        result = calculate_aca_subsidy(
            magi=D("100000"),
            filing_status="mfj",
            tax_year=TAX_YEAR,
        )
        assert result.cliff_magi == CLIFF_MFJ
        assert result.is_eligible is True
        assert result.distance_to_cliff == D("28600")

    def test_mfj_over_cliff_ineligible(self):
        result = calculate_aca_subsidy(
            magi=CLIFF_MFJ + D("1"),
            filing_status="mfj",
            tax_year=TAX_YEAR,
        )
        assert result.is_eligible is False
        assert result.aptc_annual == D("0")
        assert result.distance_to_cliff == D("-1")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_unsupported_tax_year_raises():
    with pytest.raises(ValueError, match="Unsupported tax year"):
        calculate_aca_subsidy(
            magi=D("50000"),
            filing_status="single",
            tax_year=2099,
        )


def test_invalid_filing_status_raises():
    with pytest.raises(ValueError, match="Unsupported filing status"):
        calculate_aca_subsidy(
            magi=D("50000"),
            filing_status="mfs",
            tax_year=TAX_YEAR,
        )
