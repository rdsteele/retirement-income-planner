"""Unit tests for services/federal_tax.py.

Test cases are derived from the worked examples in specs/federal_tax.md.
All expected values are hand-verified against the spec.
"""

from decimal import Decimal

import pytest

from services.federal_tax import BracketDetail, calculate_federal_tax


def dec(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# Example 1 — Single, ordinary income in multiple brackets
#             Preferential income fully in the 15% LTCG bracket
# ---------------------------------------------------------------------------

class TestExample1SingleOrdinaryMultiBrackets:
    def setup_method(self):
        self.result = calculate_federal_tax(
            ordinary_income=dec("60000"),
            preferential_income=dec("10000"),
            filing_status="single",
            tax_year=2025,
        )

    def test_ordinary_income_tax(self):
        assert self.result.ordinary_income_tax == dec("8115")

    def test_preferential_income_tax(self):
        assert self.result.preferential_income_tax == dec("1500")

    def test_total_tax(self):
        assert self.result.total_tax == dec("9615")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.1374")

    def test_marginal_bracket_rate(self):
        assert self.result.marginal_bracket_rate == dec("0.22")

    def test_bracket_breakdown_length(self):
        assert len(self.result.bracket_breakdown) == 3

    def test_bracket_breakdown_10pct(self):
        b = self.result.bracket_breakdown[0]
        assert b.rate == dec("0.10")
        assert b.income_taxed == dec("11925")
        assert b.tax_amount == dec("1193")

    def test_bracket_breakdown_12pct(self):
        b = self.result.bracket_breakdown[1]
        assert b.rate == dec("0.12")
        assert b.income_taxed == dec("36550")
        assert b.tax_amount == dec("4386")

    def test_bracket_breakdown_22pct(self):
        b = self.result.bracket_breakdown[2]
        assert b.rate == dec("0.22")
        assert b.income_taxed == dec("11525")
        assert b.tax_amount == dec("2536")


# ---------------------------------------------------------------------------
# Example 2 — MFJ, ordinary income spans multiple brackets
# ---------------------------------------------------------------------------

class TestExample2MFJOrdinaryMultiBrackets:
    def setup_method(self):
        self.result = calculate_federal_tax(
            ordinary_income=dec("100000"),
            preferential_income=dec("20000"),
            filing_status="mfj",
            tax_year=2025,
        )

    def test_ordinary_income_tax(self):
        assert self.result.ordinary_income_tax == dec("11828")

    def test_preferential_income_tax(self):
        assert self.result.preferential_income_tax == dec("3000")

    def test_total_tax(self):
        assert self.result.total_tax == dec("14828")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.1236")

    def test_marginal_bracket_rate(self):
        assert self.result.marginal_bracket_rate == dec("0.22")

    def test_bracket_breakdown(self):
        bd = self.result.bracket_breakdown
        assert len(bd) == 3
        assert bd[0] == BracketDetail(dec("0.10"), dec("23850"), dec("2385"))
        assert bd[1] == BracketDetail(dec("0.12"), dec("73100"), dec("8772"))
        assert bd[2] == BracketDetail(dec("0.22"), dec("3050"),  dec("671"))


# ---------------------------------------------------------------------------
# Example 3 — Single, preferential income straddles the 0%/15% LTCG boundary
# ---------------------------------------------------------------------------

class TestExample3PreferentialStraddlesBoundary:
    def setup_method(self):
        self.result = calculate_federal_tax(
            ordinary_income=dec("40000"),
            preferential_income=dec("20000"),
            filing_status="single",
            tax_year=2025,
        )

    def test_ordinary_income_tax(self):
        assert self.result.ordinary_income_tax == dec("4562")

    def test_preferential_income_tax(self):
        assert self.result.preferential_income_tax == dec("1748")

    def test_total_tax(self):
        assert self.result.total_tax == dec("6310")

    def test_effective_rate(self):
        assert self.result.effective_rate == dec("0.1052")

    def test_marginal_bracket_rate(self):
        assert self.result.marginal_bracket_rate == dec("0.12")

    def test_bracket_breakdown(self):
        bd = self.result.bracket_breakdown
        assert len(bd) == 2
        assert bd[0] == BracketDetail(dec("0.10"), dec("11925"), dec("1193"))
        assert bd[1] == BracketDetail(dec("0.12"), dec("28075"), dec("3369"))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_ordinary_income_defaults_marginal_rate(self):
        result = calculate_federal_tax(dec("0"), dec("10000"), "single", 2025)
        assert result.ordinary_income_tax == dec("0")
        assert result.marginal_bracket_rate == dec("0.10")

    def test_zero_ordinary_income_preferential_starts_from_bottom(self):
        # $10,000 preferential with $0 ordinary — fully in 0% LTCG bracket
        result = calculate_federal_tax(dec("0"), dec("10000"), "single", 2025)
        assert result.preferential_income_tax == dec("0")
        assert result.total_tax == dec("0")

    def test_zero_preferential_income(self):
        result = calculate_federal_tax(dec("50000"), dec("0"), "single", 2025)
        assert result.preferential_income_tax == dec("0")

    def test_both_zero(self):
        result = calculate_federal_tax(dec("0"), dec("0"), "single", 2025)
        assert result.total_tax == dec("0")
        assert result.effective_rate == dec("0")
        assert result.bracket_breakdown == []

    def test_unsupported_tax_year(self):
        with pytest.raises(ValueError, match="Unsupported tax year"):
            calculate_federal_tax(dec("50000"), dec("0"), "single", 2099)

    def test_unsupported_filing_status(self):
        with pytest.raises(ValueError, match="Unsupported filing status"):
            calculate_federal_tax(dec("50000"), dec("0"), "mfs", 2025)

    def test_income_in_top_bracket(self):
        result = calculate_federal_tax(dec("700000"), dec("0"), "single", 2025)
        assert result.marginal_bracket_rate == dec("0.37")
        assert result.ordinary_income_tax > dec("0")
        assert result.bracket_breakdown[-1].rate == dec("0.37")

    def test_preferential_income_in_twenty_percent_ltcg_bracket(self):
        # ordinary=$500,000 pushes stack base into the 15%/20% LTCG boundary ($533,400)
        # preferential $100,000 straddles: $33,400 at 15% + $66,600 at 20%
        # exercises the top-bracket path where b_to is None
        result = calculate_federal_tax(dec("500000"), dec("100000"), "single", 2025)
        assert result.preferential_income_tax == dec("18330")


# ---------------------------------------------------------------------------
# Federal 2026 — IRS Rev. Proc. 2025-32
#   Standard deduction single: $16,100
#   Ordinary bracket 10%/12% crossover: $12,225
# ---------------------------------------------------------------------------

class TestFederal2026Data:
    def test_standard_deduction_single(self):
        import json
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "data/brackets/federal_2026.json"
        data = json.loads(path.read_text())
        assert data["standard_deduction"]["single"] == "16100"

    def test_first_bracket_top_single(self):
        # At exactly $12,225 of taxable ordinary income (the 2026 10% ceiling),
        # all income falls in the 10% bracket.
        # Tax = 12,225 × 0.10 = 1222.5 → ROUND_HALF_UP = $1,223
        result = calculate_federal_tax(
            ordinary_income=dec("12225"),
            preferential_income=dec("0"),
            filing_status="single",
            tax_year=2026,
        )
        assert len(result.bracket_breakdown) == 1
        assert result.bracket_breakdown[0].rate == dec("0.10")
        assert result.bracket_breakdown[0].income_taxed == dec("12225")
        assert result.bracket_breakdown[0].tax_amount == dec("1223")
