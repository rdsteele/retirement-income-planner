# Scenario Test: IRMAA surcharge data matches the published CMS tables
#
# Source: CMS fact sheet "Medicare Parts A & B Premiums and Deductibles" for each year.
# The amounts are the monthly Part B and Part D income-related adjustment per person for
# each tier above the matching entry of irmaa_thresholds; they are the same for single and
# joint filers.
#
#   premium year 2025 Part B: 74.00 / 185.00 / 295.90 / 406.90 / 443.90
#                     Part D: 13.70 / 35.30 / 57.00 / 78.60 / 85.80
#   premium year 2026 Part B: 81.20 / 202.90 / 324.60 / 446.30 / 487.00
#                     Part D: 14.50 / 37.50 / 60.40 / 83.30 / 91.00
#   premium year 2027 Part B: 83.70 / 209.40 / 335.00 / 460.60 / 502.40
#                     Part D: 15.40 / 39.70 / 64.00 / 88.30 / 96.40

from decimal import Decimal

import pytest

from services.data_loader import load_federal_data, load_irmaa_data

_PUBLISHED = {
    2025: {
        "part_b": ["74.00", "185.00", "295.90", "406.90", "443.90"],
        "part_d": ["13.70", "35.30", "57.00", "78.60", "85.80"],
    },
    2026: {
        "part_b": ["81.20", "202.90", "324.60", "446.30", "487.00"],
        "part_d": ["14.50", "37.50", "60.40", "83.30", "91.00"],
    },
    2027: {
        "part_b": ["83.70", "209.40", "335.00", "460.60", "502.40"],
        "part_d": ["15.40", "39.70", "64.00", "88.30", "96.40"],
    },
}


@pytest.mark.parametrize(
    ("year", "part"), [(y, p) for y, by_part in _PUBLISHED.items() for p in by_part]
)
def test_surcharges_match_the_published_table(year, part):
    stored = load_irmaa_data(year)["monthly_surcharge"][part]
    assert [Decimal(a) for a in stored] == [Decimal(a) for a in _PUBLISHED[year][part]]


@pytest.mark.parametrize("year", sorted(_PUBLISHED))
@pytest.mark.parametrize("part", ["part_b", "part_d"])
def test_one_surcharge_per_threshold(year, part):
    thresholds = load_federal_data(year)["irmaa_thresholds"]
    stored = load_irmaa_data(year)["monthly_surcharge"][part]
    assert all(len(stored) == len(tiers) for tiers in thresholds.values())


@pytest.mark.parametrize("year", sorted(_PUBLISHED))
def test_surcharges_rise_with_each_tier(year):
    for part in ("part_b", "part_d"):
        amounts = [Decimal(a) for a in load_irmaa_data(year)["monthly_surcharge"][part]]
        assert amounts == sorted(amounts)


def test_unknown_year_is_rejected():
    with pytest.raises(ValueError, match="No IRMAA data"):
        load_irmaa_data(1900)
