# Scenario Tests: Social Security Taxability — Torpedo Reference Table
#
# Source: Torpedo reference table in specs/social_security.md.
# Purpose: Regression anchors for the SS provisional income formula across
#          the full income range: below threshold, 50% tier, 85% tier, and cap.
#
# Fixed parameters for all rows:
#   ss_benefit:           $24,000
#   tax_exempt_interest:  $0
#   filing_status:        "single"
#   agi_excluding_ss:     ordinary income value from table

from decimal import Decimal

import pytest

from services.social_security import calculate_social_security_taxability

D = Decimal

SS_BENEFIT = D("24000")
TAX_EXEMPT = D("0")
FILING_STATUS = "single"

# Tolerance constants
TAXABLE_SS_TOLERANCE = D("1")  # whole-dollar ROUND_HALF_UP rounding
INCLUSION_RATE_TOLERANCE = D("0.0001")  # 4 decimal-place rounding

# ── Reference table ───────────────────────────────────────────────────────────
# (ordinary_income, expected_provisional, expected_taxable_ss, expected_inclusion_rate)

_TABLE = [
    (D("10000"), D("22000"), D("0"), D("0.0000")),
    (D("15000"), D("27000"), D("1000"), D("0.0417")),
    (D("20000"), D("32000"), D("3500"), D("0.1458")),
    (D("22000"), D("34000"), D("4500"), D("0.1875")),
    (D("24000"), D("36000"), D("6200"), D("0.2583")),
    (D("26000"), D("38000"), D("7900"), D("0.3292")),
    (D("28000"), D("40000"), D("9600"), D("0.4000")),
    (D("30000"), D("42000"), D("11300"), D("0.4708")),
    (D("35000"), D("47000"), D("15550"), D("0.6479")),
    (D("40000"), D("52000"), D("19800"), D("0.8250")),
    (D("50000"), D("62000"), D("20400"), D("0.8500")),
]

_IDS = [f"ordinary={row[0]}" for row in _TABLE]


@pytest.mark.parametrize(
    "ordinary_income,exp_provisional,exp_taxable_ss,exp_inclusion_rate",
    _TABLE,
    ids=_IDS,
)
def test_torpedo_reference_table(
    ordinary_income, exp_provisional, exp_taxable_ss, exp_inclusion_rate
):
    result = calculate_social_security_taxability(
        ss_benefit=SS_BENEFIT,
        agi_excluding_ss=ordinary_income,
        tax_exempt_interest=TAX_EXEMPT,
        filing_status=FILING_STATUS,
    )

    assert result.provisional_income == exp_provisional, (
        f"provisional_income mismatch at ordinary={ordinary_income}: "
        f"got {result.provisional_income}, expected {exp_provisional}"
    )

    assert abs(result.taxable_ss - exp_taxable_ss) <= TAXABLE_SS_TOLERANCE, (
        f"taxable_ss mismatch at ordinary={ordinary_income}: "
        f"got {result.taxable_ss}, expected {exp_taxable_ss} "
        f"(tolerance ±{TAXABLE_SS_TOLERANCE})"
    )

    assert abs(result.inclusion_rate - exp_inclusion_rate) <= INCLUSION_RATE_TOLERANCE, (
        f"inclusion_rate mismatch at ordinary={ordinary_income}: "
        f"got {result.inclusion_rate}, expected {exp_inclusion_rate} "
        f"(tolerance ±{INCLUSION_RATE_TOLERANCE})"
    )


# ── Tier classification ───────────────────────────────────────────────────────
# Row 1  (PI=22000): "none"           — below $25,000 tier-1 threshold
# Rows 2–3 (PI=27000–32000): "fifty_percent"  — strictly between tier-1 and tier-2
# Rows 4–11 (PI=34000–62000): "eighty_five_percent" — at or above tier-2
#   Note: PI=$34,000 (ordinary=$22,000) is exactly at the tier-2 threshold.
#   The service uses >= so it is classified as eighty_five_percent. The
#   taxable_ss amount ($4,500) is identical to what the 50% formula would give
#   at that boundary, so only the tier label differs.

_TIER_TABLE = [
    (D("10000"), "none"),
    (D("15000"), "fifty_percent"),
    (D("20000"), "fifty_percent"),
    (D("22000"), "eighty_five_percent"),
    (D("24000"), "eighty_five_percent"),
    (D("26000"), "eighty_five_percent"),
    (D("28000"), "eighty_five_percent"),
    (D("30000"), "eighty_five_percent"),
    (D("35000"), "eighty_five_percent"),
    (D("40000"), "eighty_five_percent"),
    (D("50000"), "eighty_five_percent"),
]

_TIER_IDS = [f"ordinary={row[0]}" for row in _TIER_TABLE]


@pytest.mark.parametrize(
    "ordinary_income,expected_tier",
    _TIER_TABLE,
    ids=_TIER_IDS,
)
def test_tier_classification(ordinary_income, expected_tier):
    result = calculate_social_security_taxability(
        ss_benefit=SS_BENEFIT,
        agi_excluding_ss=ordinary_income,
        tax_exempt_interest=TAX_EXEMPT,
        filing_status=FILING_STATUS,
    )

    assert result.tier == expected_tier, (
        f"tier mismatch at ordinary={ordinary_income} "
        f"(PI={result.provisional_income}): "
        f"got {result.tier!r}, expected {expected_tier!r}"
    )
