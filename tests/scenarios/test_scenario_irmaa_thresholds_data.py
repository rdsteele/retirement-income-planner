# Scenario Test: IRMAA threshold data matches the published SSA tables
#
# Source: SSA POMS HI 01101.020 (IRMAA sliding scale tables). The first number in each
# list is where the first surcharge tier starts (MAGI above it); the last is where the top
# tier starts. Each premium year uses income from two years earlier, and the thresholds
# are indexed every year, so a year's file must hold that year's table, not a copy of the
# year before.
#
#   premium year 2025 single: 106,000 / 133,000 / 167,000 / 200,000 / 500,000
#                    joint:   212,000 / 266,000 / 334,000 / 400,000 / 750,000
#   premium year 2026 single: 109,000 / 137,000 / 171,000 / 205,000 / 500,000
#                    joint:   218,000 / 274,000 / 342,000 / 410,000 / 750,000

from decimal import Decimal

import pytest

from services.data_loader import load_federal_data

_PUBLISHED = {
    2025: {
        "single": [106000, 133000, 167000, 200000, 500000],
        "mfj": [212000, 266000, 334000, 400000, 750000],
    },
    2026: {
        "single": [109000, 137000, 171000, 205000, 500000],
        "mfj": [218000, 274000, 342000, 410000, 750000],
    },
}


@pytest.mark.parametrize(
    ("year", "status"), [(y, s) for y, by_status in _PUBLISHED.items() for s in by_status]
)
def test_thresholds_match_the_published_table(year, status):
    stored = load_federal_data(year)["irmaa_thresholds"][status]
    assert [Decimal(t) for t in stored] == [Decimal(t) for t in _PUBLISHED[year][status]]


def test_each_year_differs_from_the_year_before():
    assert (
        load_federal_data(2026)["irmaa_thresholds"]["single"]
        != load_federal_data(2025)["irmaa_thresholds"]["single"]
    )
