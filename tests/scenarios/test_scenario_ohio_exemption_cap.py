# Scenario Test: Ohio personal exemption income cap, exactly at the boundary
#
# R.C. 5747.025: the personal exemption applies only when modified AGI is less than
# 750,000 for 2025, and less than 500,000 for 2026 and after. The exemption amounts for
# these years are unchanged by inflation (H.B. 96 suspends indexing), so a taxpayer above
# 80,000 gets 1,900 per person (3,800 for a joint return) and one at the cap gets none.
# Nonbusiness income tax: a single table for every filing status.
#
# Single, 2026 (tax = 332 + 2.75% of the amount over 26,050):
#   AGI 499,999: base 499,999 - 1,900 = 498,099; 332 + 0.0275 x 472,049 = 13,313.35 -> 13,313
#   AGI 500,000: no exemption, base 500,000; 332 + 0.0275 x 473,950 = 13,366.13 -> 13,366
# Joint, 2026:
#   AGI 499,999: base 499,999 - 3,800 = 496,199; 332 + 0.0275 x 470,149 = 13,261.10 -> 13,261
# Single, 2025 (above 100,000: 2,394.32 + 3.125% of the amount over 100,000):
#   AGI 749,999: base 748,099; 2,394.32 + 0.03125 x 648,099 = 22,647.41 -> 22,647
#   AGI 750,000: no exemption;  2,394.32 + 0.03125 x 650,000 = 22,706.82 -> 22,707

from decimal import Decimal

import pytest

from services.ohio_tax import calculate_ohio_tax

D = Decimal
_ZERO = D("0")


def _ohio(agi: str, year: int, status: str = "single"):
    return calculate_ohio_tax(
        federal_agi=D(agi),
        gross_medical_expenses=_ZERO,
        qualifying_retirement_income=_ZERO,
        ss_taxable_federal=_ZERO,
        tax_year=year,
        filing_status=status,
    )


@pytest.mark.parametrize(
    ("agi", "year", "status", "exemption", "tax"),
    [
        ("499999", 2026, "single", "1900", "13313"),
        ("500000", 2026, "single", "0", "13366"),
        ("499999", 2026, "mfj", "3800", "13261"),
        ("500000", 2026, "mfj", "0", "13366"),
        ("749999", 2025, "single", "1900", "22647"),
        ("750000", 2025, "single", "0", "22707"),
    ],
)
def test_exemption_and_tax_at_the_cap(agi, year, status, exemption, tax):
    result = _ohio(agi, year, status)
    assert result.personal_exemption == D(exemption)
    assert result.ohio_tax == D(tax)


def test_the_2026_cap_is_lower_than_the_2025_cap():
    # 600,000 still gets the exemption in 2025 but not in 2026
    assert _ohio("600000", 2025).personal_exemption == D("1900")
    assert _ohio("600000", 2026).personal_exemption == D("0")
