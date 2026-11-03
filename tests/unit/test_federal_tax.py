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
        assert bd[0] == BracketDetail(
            dec("0.10"), dec("23850"), dec("2385"), dec("0"), dec("23850")
        )
        assert bd[1] == BracketDetail(
            dec("0.12"), dec("73100"), dec("8772"), dec("23850"), dec("96950")
        )
        assert bd[2] == BracketDetail(
            dec("0.22"), dec("3050"), dec("671"), dec("96950"), dec("206700")
        )


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
        assert bd[0] == BracketDetail(
            dec("0.10"), dec("11925"), dec("1193"), dec("0"), dec("11925")
        )
        assert bd[1] == BracketDetail(
            dec("0.12"), dec("28075"), dec("3369"), dec("11925"), dec("48475")
        )


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
        # At exactly $12,400 of taxable ordinary income (the 2026 10% ceiling),
        # all income falls in the 10% bracket.
        # Tax = 12,400 × 0.10 = 1240.00 → $1,240
        result = calculate_federal_tax(
            ordinary_income=dec("12400"),
            preferential_income=dec("0"),
            filing_status="single",
            tax_year=2026,
        )
        assert len(result.bracket_breakdown) == 1
        assert result.bracket_breakdown[0].rate == dec("0.10")
        assert result.bracket_breakdown[0].income_taxed == dec("12400")
        assert result.bracket_breakdown[0].tax_amount == dec("1240")


# ---------------------------------------------------------------------------
# split_taxable_income — unused deductions offset preferential income
# ---------------------------------------------------------------------------

from services.federal_tax import split_taxable_income  # noqa: E402


class TestSplitTaxableIncome:
    def test_deduction_smaller_than_ordinary_leaves_preferential_untouched(self):
        ordinary, pref = split_taxable_income(dec("30000"), dec("10000"), dec("16100"))
        assert ordinary == dec("13900")
        assert pref == dec("10000")

    def test_deduction_exceeding_ordinary_reduces_preferential(self):
        # RR scenario: ordinary 330 after adjustments, deduction 16,100, pref 39,947
        ordinary, pref = split_taxable_income(dec("330"), dec("39947"), dec("16100"))
        assert ordinary == dec("0")
        assert pref == dec("24177")

    def test_deduction_exceeding_all_income_gives_zero_taxable(self):
        ordinary, pref = split_taxable_income(dec("1000"), dec("2000"), dec("16100"))
        assert ordinary == dec("0")
        assert pref == dec("0")

    def test_zero_ordinary_all_deduction_applies_to_preferential(self):
        ordinary, pref = split_taxable_income(dec("0"), dec("60000"), dec("16100"))
        assert ordinary == dec("0")
        assert pref == dec("43900")


# ---------------------------------------------------------------------------
# Bracket breakdown rows — shared by federal tax and tax detail
# ---------------------------------------------------------------------------

from services.federal_tax import (  # noqa: E402
    _apply_ordinary_brackets,
    _apply_preferential_brackets,
    make_bracket_detail,
)

_LIT_ORDINARY = [
    {"rate": "0.10", "from": "0", "to": "10000"},
    {"rate": "0.20", "from": "10000", "to": "50000"},
    {"rate": "0.30", "from": "50000", "to": None},
]
_LIT_PREFERENTIAL = [
    {"rate": "0.00", "from": "0", "to": "40000"},
    {"rate": "0.15", "from": "40000", "to": None},
]


class TestMakeBracketDetail:
    def test_computes_rounded_tax_and_reports_bounds(self):
        row = make_bracket_detail(_LIT_ORDINARY[1], dec("20000"))
        assert (row.rate, row.income_taxed, row.tax_amount) == (
            dec("0.20"),
            dec("20000"),
            dec("4000"),
        )
        assert (row.bracket_from, row.bracket_to) == (dec("10000"), dec("50000"))

    def test_unbounded_top_bracket_has_no_upper_bound(self):
        assert make_bracket_detail(_LIT_ORDINARY[2], dec("5")).bracket_to is None

    def test_rounds_half_up(self):
        assert make_bracket_detail(_LIT_ORDINARY[0], dec("5")).tax_amount == dec("1")  # 0.5 -> 1


class TestOrdinaryBracketRows:
    def test_income_spanning_two_brackets(self):
        _, _, rows = _apply_ordinary_brackets(dec("30000"), _LIT_ORDINARY)
        assert [(r.rate, r.income_taxed, r.tax_amount) for r in rows] == [
            (dec("0.10"), dec("10000"), dec("1000")),
            (dec("0.20"), dec("20000"), dec("4000")),
        ]

    def test_rows_report_bracket_bounds(self):
        _, _, rows = _apply_ordinary_brackets(dec("30000"), _LIT_ORDINARY)
        assert (rows[1].bracket_from, rows[1].bracket_to) == (dec("10000"), dec("50000"))

    def test_zero_income_has_no_rows(self):
        assert _apply_ordinary_brackets(dec("0"), _LIT_ORDINARY)[2] == []

    def test_top_bracket_is_unbounded(self):
        _, _, rows = _apply_ordinary_brackets(dec("60000"), _LIT_ORDINARY)
        assert rows[-1].rate == dec("0.30")
        assert rows[-1].bracket_to is None
        assert rows[-1].income_taxed == dec("10000")

    def test_marginal_rate_is_last_bracket_with_income(self):
        assert _apply_ordinary_brackets(dec("30000"), _LIT_ORDINARY)[1] == dec("0.20")

    def test_zero_income_marginal_rate_is_first_bracket_rate(self):
        brackets = [{"rate": "0.05", "from": "0", "to": "10000"}]
        assert _apply_ordinary_brackets(dec("0"), brackets)[1] == dec("0.05")


class TestPreferentialBracketRows:
    def test_stacks_on_top_of_ordinary_income(self):
        rows = _apply_preferential_brackets(dec("50000"), dec("5000"), _LIT_PREFERENTIAL)
        assert [(r.rate, r.income_taxed, r.tax_amount) for r in rows] == [
            (dec("0.00"), dec("35000"), dec("0")),
            (dec("0.15"), dec("15000"), dec("2250")),
        ]

    def test_skips_bracket_filled_by_ordinary_income(self):
        rows = _apply_preferential_brackets(dec("10000"), dec("45000"), _LIT_PREFERENTIAL)
        assert [(r.rate, r.income_taxed, r.tax_amount) for r in rows] == [
            (dec("0.15"), dec("10000"), dec("1500")),
        ]

    def test_zero_preferential_has_no_rows(self):
        assert _apply_preferential_brackets(dec("0"), dec("5000"), _LIT_PREFERENTIAL) == []


class TestFederalResultPreferentialBreakdown:
    def test_result_carries_preferential_rows_that_sum_to_tax(self):
        result = calculate_federal_tax(dec("5000"), dec("60000"), "single", 2026)
        assert result.preferential_breakdown
        assert sum(r.tax_amount for r in result.preferential_breakdown) == (
            result.preferential_income_tax
        )

    def test_no_preferential_income_has_no_rows(self):
        result = calculate_federal_tax(dec("30000"), dec("0"), "single", 2026)
        assert result.preferential_breakdown == []
