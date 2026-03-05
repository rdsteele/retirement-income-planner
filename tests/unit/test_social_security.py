"""Unit tests for services/social_security.py.

Test cases are derived from the worked examples, edge cases table, and tax
torpedo reference table in specs/social_security.md. All expected values are
hand-verified against the spec.
"""

from decimal import Decimal

import pytest

from services.social_security import SocialSecurityResult, calculate_social_security_taxability


def D(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# Example 1 — Below threshold, no taxable SS
# Single, ss=20000, agi_excl=15000, tei=0 → PI=25000 (exactly at threshold)
# ---------------------------------------------------------------------------

class TestExample1BelowThreshold:
    def setup_method(self):
        self.result = calculate_social_security_taxability(
            ss_benefit=D("20000"),
            agi_excluding_ss=D("15000"),
            tax_exempt_interest=D("0"),
            filing_status="single",
        )

    def test_provisional_income(self):
        assert self.result.provisional_income == D("25000")

    def test_taxable_ss(self):
        assert self.result.taxable_ss == D("0")

    def test_inclusion_rate(self):
        assert self.result.inclusion_rate == D("0.0000")

    def test_tier(self):
        assert self.result.tier == "none"


# ---------------------------------------------------------------------------
# Example 2 — In 50% tier, partial inclusion
# Single, ss=20000, agi_excl=20000, tei=0 → PI=30000
# ---------------------------------------------------------------------------

class TestExample2FiftyPercentPartial:
    def setup_method(self):
        self.result = calculate_social_security_taxability(
            ss_benefit=D("20000"),
            agi_excluding_ss=D("20000"),
            tax_exempt_interest=D("0"),
            filing_status="single",
        )

    def test_provisional_income(self):
        assert self.result.provisional_income == D("30000")

    def test_taxable_ss(self):
        assert self.result.taxable_ss == D("2500")

    def test_inclusion_rate(self):
        assert self.result.inclusion_rate == D("0.1250")

    def test_tier(self):
        assert self.result.tier == "fifty_percent"


# ---------------------------------------------------------------------------
# Example 3 — PI exceeds tier 2; 85% tier applies
# Single, ss=20000, agi_excl=30000, tei=0 → PI=40000
# ---------------------------------------------------------------------------

class TestExample3EightyFivePercentTierEntry:
    def setup_method(self):
        self.result = calculate_social_security_taxability(
            ss_benefit=D("20000"),
            agi_excluding_ss=D("30000"),
            tax_exempt_interest=D("0"),
            filing_status="single",
        )

    def test_provisional_income(self):
        assert self.result.provisional_income == D("40000")

    def test_taxable_ss(self):
        assert self.result.taxable_ss == D("9600")

    def test_inclusion_rate(self):
        assert self.result.inclusion_rate == D("0.4800")

    def test_tier(self):
        assert self.result.tier == "eighty_five_percent"


# ---------------------------------------------------------------------------
# Example 4 — In 85% tier, partial inclusion
# Single, ss=20000, agi_excl=35000, tei=0 → PI=45000
# ---------------------------------------------------------------------------

class TestExample4EightyFivePercentPartial:
    def setup_method(self):
        self.result = calculate_social_security_taxability(
            ss_benefit=D("20000"),
            agi_excluding_ss=D("35000"),
            tax_exempt_interest=D("0"),
            filing_status="single",
        )

    def test_provisional_income(self):
        assert self.result.provisional_income == D("45000")

    def test_taxable_ss(self):
        assert self.result.taxable_ss == D("13850")

    def test_inclusion_rate(self):
        assert self.result.inclusion_rate == D("0.6925")

    def test_tier(self):
        assert self.result.tier == "eighty_five_percent"


# ---------------------------------------------------------------------------
# Example 5 — Maximum 85% reached
# Single, ss=20000, agi_excl=50000, tei=0 → PI=60000
# ---------------------------------------------------------------------------

class TestExample5MaximumEightyFive:
    def setup_method(self):
        self.result = calculate_social_security_taxability(
            ss_benefit=D("20000"),
            agi_excluding_ss=D("50000"),
            tax_exempt_interest=D("0"),
            filing_status="single",
        )

    def test_provisional_income(self):
        assert self.result.provisional_income == D("60000")

    def test_taxable_ss(self):
        assert self.result.taxable_ss == D("17000")

    def test_inclusion_rate(self):
        assert self.result.inclusion_rate == D("0.8500")

    def test_tier(self):
        assert self.result.tier == "eighty_five_percent"


# ---------------------------------------------------------------------------
# Example 6 — Tax-exempt interest increases provisional income
# Single, ss=20000, agi_excl=18000, tei=5000 → PI=33000
# ---------------------------------------------------------------------------

class TestExample6TaxExemptInterest:
    def setup_method(self):
        self.result = calculate_social_security_taxability(
            ss_benefit=D("20000"),
            agi_excluding_ss=D("18000"),
            tax_exempt_interest=D("5000"),
            filing_status="single",
        )

    def test_provisional_income(self):
        assert self.result.provisional_income == D("33000")

    def test_taxable_ss(self):
        assert self.result.taxable_ss == D("4000")

    def test_inclusion_rate(self):
        assert self.result.inclusion_rate == D("0.2000")

    def test_tier(self):
        assert self.result.tier == "fifty_percent"


# ---------------------------------------------------------------------------
# Example 7 — Zero SS benefit
# ---------------------------------------------------------------------------

class TestExample7ZeroSSBenefit:
    def setup_method(self):
        self.result = calculate_social_security_taxability(
            ss_benefit=D("0"),
            agi_excluding_ss=D("50000"),
            tax_exempt_interest=D("0"),
            filing_status="single",
        )

    def test_provisional_income(self):
        assert self.result.provisional_income == D("50000")

    def test_taxable_ss(self):
        assert self.result.taxable_ss == D("0")

    def test_inclusion_rate(self):
        assert self.result.inclusion_rate == D("0")

    def test_tier(self):
        assert self.result.tier == "none"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_pi_exactly_at_tier_1_threshold_is_none(self):
        # PI = 25000 exactly → taxable_ss = 0, tier = "none"
        result = calculate_social_security_taxability(D("20000"), D("15000"), D("0"), "single")
        assert result.taxable_ss == D("0")
        assert result.tier == "none"

    def test_pi_exactly_at_tier_2_threshold_uses_eighty_five_tier(self):
        # PI = 34000 exactly → 85% tier formula applies
        # agi_excl=22000, ss=24000 → PI=22000+0+12000=34000
        result = calculate_social_security_taxability(D("24000"), D("22000"), D("0"), "single")
        assert result.provisional_income == D("34000")
        assert result.tier == "eighty_five_percent"
        # tier_2_amount = 0.85*(34000-34000)=0; max_tier_1=min(12000,4500)=4500; taxable=4500
        assert result.taxable_ss == D("4500")

    def test_mfj_uses_higher_thresholds(self):
        # MFJ tier_1=32000, tier_2=44000
        # ss=24000, agi_excl=20000, tei=0 → PI=20000+12000=32000 → exactly at tier_1 → none
        result = calculate_social_security_taxability(D("24000"), D("20000"), D("0"), "mfj")
        assert result.provisional_income == D("32000")
        assert result.taxable_ss == D("0")
        assert result.tier == "none"

    def test_mfj_in_fifty_percent_tier(self):
        # MFJ, ss=24000, agi_excl=25000, tei=0 → PI=25000+12000=37000 → 50% tier
        # taxable = 0.50*(37000-32000)=2500; cap=0.50*24000=12000 → not hit
        result = calculate_social_security_taxability(D("24000"), D("25000"), D("0"), "mfj")
        assert result.provisional_income == D("37000")
        assert result.taxable_ss == D("2500")
        assert result.tier == "fifty_percent"

    def test_unsupported_filing_status_raises(self):
        with pytest.raises(ValueError, match="Unsupported filing status"):
            calculate_social_security_taxability(D("20000"), D("30000"), D("0"), "mfs")

    def test_high_income_taxable_ss_capped_at_eighty_five_pct(self):
        # Very high income — taxable_ss must not exceed 0.85 * ss_benefit
        result = calculate_social_security_taxability(D("20000"), D("200000"), D("0"), "single")
        assert result.taxable_ss == D("17000")
        assert result.inclusion_rate == D("0.8500")


# ---------------------------------------------------------------------------
# Tax torpedo reference table — ss=24000, single, tei=0
# Selected rows to validate the torpedo progression without duplicating
# rows already covered by examples above.
# ---------------------------------------------------------------------------

class TestTaxTorpedoTable:
    SS = D("24000")

    def _calc(self, ordinary_income: str) -> SocialSecurityResult:
        return calculate_social_security_taxability(
            ss_benefit=self.SS,
            agi_excluding_ss=D(ordinary_income),
            tax_exempt_interest=D("0"),
            filing_status="single",
        )

    def test_row_ordinary_10000(self):
        r = self._calc("10000")
        assert r.provisional_income == D("22000")
        assert r.taxable_ss == D("0")
        assert r.tier == "none"

    def test_row_ordinary_15000(self):
        r = self._calc("15000")
        assert r.provisional_income == D("27000")
        assert r.taxable_ss == D("1000")
        assert r.tier == "fifty_percent"

    def test_row_ordinary_20000(self):
        r = self._calc("20000")
        assert r.provisional_income == D("32000")
        assert r.taxable_ss == D("3500")
        assert r.tier == "fifty_percent"

    def test_row_ordinary_26000(self):
        r = self._calc("26000")
        assert r.provisional_income == D("38000")
        assert r.taxable_ss == D("7900")
        assert r.tier == "eighty_five_percent"

    def test_row_ordinary_28000(self):
        r = self._calc("28000")
        assert r.provisional_income == D("40000")
        assert r.taxable_ss == D("9600")
        assert r.tier == "eighty_five_percent"

    def test_row_ordinary_35000(self):
        r = self._calc("35000")
        assert r.provisional_income == D("47000")
        assert r.taxable_ss == D("15550")
        assert r.tier == "eighty_five_percent"

    def test_row_ordinary_50000(self):
        r = self._calc("50000")
        assert r.provisional_income == D("62000")
        assert r.taxable_ss == D("20400")
        assert r.inclusion_rate == D("0.8500")
        assert r.tier == "eighty_five_percent"
