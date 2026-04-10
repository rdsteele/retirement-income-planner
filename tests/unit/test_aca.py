"""Unit tests for services/aca.py — schedule-based APTC calculation.

2026 single filer: cliff = $62,600 (from filing_status_cliffs in data).
Schedule minimum: $22,000 (Medicaid boundary).
MFJ cliff: $85,000 (from filing_status_cliffs; schedule ends at {85000, 0}).

Tests:
 1. Schedule interpolation between two points
 2. Schedule exact match on a schedule point
 3. Below lowest schedule point → zero APTC, is_eligible=False
 4. At cliff → aptc=0, last non-zero APTC as marginal spike, distance=0
 5. One dollar over cliff → zero APTC, full subsidy_loss, marginal=0
 6. Subsidy loss correct vs non-default baseline MAGI
 7. Marginal subsidy loss correct between schedule points (gradual slope)
 8. Marginal subsidy loss spikes at cliff crossing
 9. MFJ schedule populated — interpolation at $50,000
10. MFJ cliff uses schedule-derived threshold ($85,000)
11. Formula fallback — empty schedule uses applicable_percentage formula
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from services.aca import (
    _cliff_from_fpl,
    _interpolate_monthly_aptc,
    _last_nonzero_annual,
    _marginal_loss_from_schedule,
    calculate_aca_subsidy,
    get_aptc_schedule_magis,
)

D = Decimal

CLIFF_SINGLE = D("62600")
CLIFF_MFJ = D("85000")
TAX_YEAR = 2026


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
# 9. MFJ schedule populated — interpolation at $50,000
# ---------------------------------------------------------------------------


def test_mfj_schedule_at_50k():
    """MFJ schedule is populated; $50,000 is an exact schedule point → $707/month."""
    # Schedule entry: {magi: 50000, monthly_aptc: 707}
    # aptc_annual = 707 × 12 = 8484
    result = calculate_aca_subsidy(
        magi=D("50000"),
        filing_status="mfj",
        tax_year=TAX_YEAR,
    )
    assert result.aptc_monthly == D("707")
    assert result.aptc_annual == D("8484")
    assert result.is_eligible is True
    assert result.cliff_magi == CLIFF_MFJ


# ---------------------------------------------------------------------------
# 10. MFJ cliff uses schedule-derived threshold ($85,000)
# ---------------------------------------------------------------------------


class TestMFJCliff:
    def test_cliff_is_mfj_threshold(self):
        # At $80,000: below the $85,000 cliff, eligible
        result = calculate_aca_subsidy(
            magi=D("80000"),
            filing_status="mfj",
            tax_year=TAX_YEAR,
        )
        assert result.cliff_magi == CLIFF_MFJ
        assert result.is_eligible is True
        assert result.distance_to_cliff == D("5000")

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


# ---------------------------------------------------------------------------
# 11. Formula fallback — empty schedule uses applicable_percentage formula
#
# Synthetic data: "single" aptc_schedule is empty, so the formula path runs.
# cliff_magi = 62600 (from filing_status_cliffs), slcsp = $10,000/year.
# applicable_percentage = 0.0996
#
# At magi=50000:
#   required = round_tax(50000 × 0.0996) = 4980
#   aptc_annual = round_tax(10000 − 4980) = 5020
#   aptc_monthly = round_tax(5020 / 12) = 418
#
# At magi=62600 (cliff):
#   cliff_aptc = round_tax(10000 − round_tax(62600 × 0.0996)) = 3765
#   marginal_subsidy_loss = 3765 (cliff spike)
#
# baseline_magi=30000:
#   baseline_aptc = round_tax(10000 − round_tax(30000 × 0.0996)) = 7012
#   subsidy_loss vs magi=50000: round_tax(7012 − 5020) = 1992
# ---------------------------------------------------------------------------

_FORMULA_DATA = {
    "filing_status_cliffs": {"single": 62600},
    "fpl_100pct": {"single": "15650", "mfj": "32150"},
    "applicable_percentage_400pct": "0.0996",
    "aptc_schedule": {"single": [], "mfj": []},
}

_SLCSP = D("10000")


class TestFormulaFallback:
    """Empty aptc_schedule → formula path in calculate_aca_subsidy."""

    def _calc(self, magi, baseline_magi=None):
        with patch("services.aca._load_aca_data", return_value=_FORMULA_DATA):
            return calculate_aca_subsidy(
                magi=magi,
                filing_status="single",
                tax_year=TAX_YEAR,
                baseline_magi=baseline_magi,
                slcsp_annual_premium=_SLCSP,
            )

    def test_eligible_below_cliff(self):
        result = self._calc(D("50000"))
        assert result.is_eligible is True
        assert result.aptc_annual == D("5020")
        assert result.aptc_monthly == D("418")
        assert result.cliff_magi == D("62600")
        assert result.distance_to_cliff == D("12600")

    def test_eligible_subsidy_loss_zero_at_own_magi(self):
        # Default baseline = aptc_annual itself → loss = 0
        result = self._calc(D("50000"))
        assert result.subsidy_loss == D("0")

    def test_at_cliff_marginal_equals_cliff_aptc(self):
        # At exactly cliff_magi: aptc=0, marginal = cliff_aptc (formula spike)
        result = self._calc(D("62600"))
        assert result.is_eligible is False
        assert result.aptc_annual == D("0")
        assert result.marginal_subsidy_loss == D("3765")

    def test_above_cliff_ineligible_marginal_zero(self):
        result = self._calc(D("70000"))
        assert result.is_eligible is False
        assert result.aptc_annual == D("0")
        assert result.marginal_subsidy_loss == D("0")

    def test_subsidy_loss_vs_explicit_baseline(self):
        # baseline_magi=30000 → baseline_aptc=7012; current_aptc=5020 → loss=1992
        result = self._calc(D("50000"), baseline_magi=D("30000"))
        assert result.subsidy_loss == D("1992")

    def test_fpl_cliff_fallback_when_no_filing_status_cliffs_key(self):
        # Covers lines 174-175: else branch when data has no filing_status_cliffs.
        # Also covers line 51: _cliff_from_fpl returns fpl_100pct × 4.
        # cliff = 15650 × 4 = 62600 (same numeric result as the data-driven cliff)
        formula_no_cliffs = {
            "fpl_100pct": {"single": "15650", "mfj": "32150"},
            "applicable_percentage_400pct": "0.0996",
            "aptc_schedule": {"single": [], "mfj": []},
        }
        with patch("services.aca._load_aca_data", return_value=formula_no_cliffs):
            result = calculate_aca_subsidy(
                magi=D("50000"),
                filing_status="single",
                tax_year=TAX_YEAR,
                slcsp_annual_premium=_SLCSP,
            )
        assert result.cliff_magi == D("62600")
        assert result.is_eligible is True


# ---------------------------------------------------------------------------
# Internal helper: _cliff_from_fpl
# ---------------------------------------------------------------------------


def test_cliff_from_fpl_multiplies_by_four():
    # Line 51: direct unit test of the helper
    assert _cliff_from_fpl(D("15650")) == D("62600")
    assert _cliff_from_fpl(D("32150")) == D("128600")


# ---------------------------------------------------------------------------
# Internal helper: _interpolate_monthly_aptc — defensive returns
# ---------------------------------------------------------------------------

_SIMPLE_SCHEDULE = [
    {"magi": 22000, "monthly_aptc": 972},
    {"magi": 35000, "monthly_aptc": 820},
]


def test_interpolate_below_first_point_returns_zero():
    # Line 70: i==0 and first pt_magi > magi → return _ZERO
    assert _interpolate_monthly_aptc(_SIMPLE_SCHEDULE, D("10000")) == D("0")


def test_interpolate_above_last_point_returns_zero():
    # Line 79: magi above all schedule points → loop ends, return _ZERO
    assert _interpolate_monthly_aptc(_SIMPLE_SCHEDULE, D("50000")) == D("0")


# ---------------------------------------------------------------------------
# Internal helper: _last_nonzero_annual — all-zero schedule
# ---------------------------------------------------------------------------


def test_last_nonzero_annual_all_zero_schedule():
    # Line 88: no non-zero monthly_aptc entry → return _ZERO
    all_zero = [
        {"magi": 22000, "monthly_aptc": 0},
        {"magi": 62600, "monthly_aptc": 0},
    ]
    assert _last_nonzero_annual(all_zero) == D("0")


# ---------------------------------------------------------------------------
# Internal helper: _marginal_loss_from_schedule — past-end return
# ---------------------------------------------------------------------------


def test_marginal_loss_above_last_interval_returns_zero():
    # Line 125: magi sits above all schedule intervals but below cliff.
    # Schedule only covers up to 35000; cliff is 62600; magi=50000 falls past
    # all (lower, upper) pairs in the loop.
    cliff = D("62600")
    assert _marginal_loss_from_schedule(_SIMPLE_SCHEDULE, D("50000"), cliff) == D("0")


# ---------------------------------------------------------------------------
# Internal helper: _last_nonzero_annual called from schedule path at cliff
# when all monthly_aptc are zero — marginal = 0
# ---------------------------------------------------------------------------


def test_all_zero_schedule_marginal_zero_at_cliff():
    # Covers line 88 via the schedule path in calculate_aca_subsidy:
    # at magi==cliff_magi with an all-zero schedule, marginal = _last_nonzero = 0.
    all_zero_data = {
        "filing_status_cliffs": {"single": 62600},
        "fpl_100pct": {"single": "15650", "mfj": "32150"},
        "applicable_percentage_400pct": "0.0996",
        "aptc_schedule": {
            "single": [
                {"magi": 22000, "monthly_aptc": 0},
                {"magi": 62600, "monthly_aptc": 0},
            ],
            "mfj": [],
        },
    }
    with patch("services.aca._load_aca_data", return_value=all_zero_data):
        result = calculate_aca_subsidy(
            magi=D("62600"),
            filing_status="single",
            tax_year=TAX_YEAR,
        )
    assert result.marginal_subsidy_loss == D("0")


# ---------------------------------------------------------------------------
# get_aptc_schedule_magis (lines 143-145)
# ---------------------------------------------------------------------------


def test_get_aptc_schedule_magis_single_2026():
    # Lines 143-145: loads schedule and returns magi list
    magis = get_aptc_schedule_magis("single", TAX_YEAR)
    assert isinstance(magis, list)
    assert D("22000") in magis
    assert D("62600") in magis


def test_get_aptc_schedule_magis_empty_when_no_schedule():
    # Empty schedule → empty list
    empty_data = {
        "fpl_100pct": {"single": "15650", "mfj": "32150"},
        "applicable_percentage_400pct": "0.0996",
        "aptc_schedule": {"single": [], "mfj": []},
    }
    with patch("services.aca._load_aca_data", return_value=empty_data):
        magis = get_aptc_schedule_magis("single", TAX_YEAR)
    assert magis == []


# ---------------------------------------------------------------------------
# Baseline_magi below schedule minimum triggers _interpolate line 70
# via the baseline calculation path in calculate_aca_subsidy
# ---------------------------------------------------------------------------


def test_baseline_below_schedule_minimum_yields_zero_baseline():
    # baseline_magi=10000 < 22000 (min_schedule_magi).
    # _interpolate_monthly_aptc(schedule, 10000) → hits line 70, returns 0.
    # baseline_aptc = 0; subsidy_loss = max(0, 0 - current_aptc) = 0.
    result = calculate_aca_subsidy(
        magi=D("35000"),
        filing_status="single",
        tax_year=TAX_YEAR,
        baseline_magi=D("10000"),
    )
    assert result.subsidy_loss == D("0")
