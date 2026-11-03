"""Unit tests for services/tax_detail.py.

Composed services (social_security, federal_tax, niit, ohio_tax) and the data
loader are mocked; no file I/O. Bracket-breakdown helpers use literal brackets.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from services.federal_tax import FederalTaxResult
from services.niit import NIITResult
from services.ohio_tax import OhioTaxResult
from services.social_security import SocialSecurityResult
from services.tax_detail import (
    _build_ordinary_breakdown,
    _build_preferential_breakdown,
    calculate_tax_detail,
)


def dec(s: str) -> Decimal:
    return Decimal(s)


_ORDINARY = [
    {"rate": "0.10", "from": "0", "to": "10000"},
    {"rate": "0.20", "from": "10000", "to": "50000"},
    {"rate": "0.30", "from": "50000", "to": None},
]
_PREFERENTIAL = [
    {"rate": "0.00", "from": "0", "to": "40000"},
    {"rate": "0.15", "from": "40000", "to": None},
]
_FEDERAL_DATA = {
    "standard_deduction": {"single": "16000", "mfj": "32000"},
    "ordinary": {"single": _ORDINARY, "mfj": _ORDINARY},
    "preferential": {"single": _PREFERENTIAL, "mfj": _PREFERENTIAL},
}


# ---------------------------------------------------------------------------
# Ordinary bracket breakdown
# ---------------------------------------------------------------------------


class TestOrdinaryBreakdown:
    def test_income_spanning_two_brackets(self):
        rows = _build_ordinary_breakdown(dec("30000"), _ORDINARY)
        assert [(r.rate, r.income_taxed, r.tax_amount) for r in rows] == [
            (dec("0.10"), dec("10000"), dec("1000")),
            (dec("0.20"), dec("20000"), dec("4000")),
        ]

    def test_rows_report_bracket_bounds(self):
        rows = _build_ordinary_breakdown(dec("30000"), _ORDINARY)
        assert (rows[1].bracket_from, rows[1].bracket_to) == (dec("10000"), dec("50000"))

    def test_zero_income_returns_single_zero_row(self):
        rows = _build_ordinary_breakdown(dec("0"), _ORDINARY)
        assert len(rows) == 1
        assert rows[0].rate == dec("0.10")
        assert rows[0].income_taxed == dec("0")
        assert rows[0].tax_amount == dec("0")

    def test_top_bracket_is_unbounded(self):
        rows = _build_ordinary_breakdown(dec("60000"), _ORDINARY)
        assert rows[-1].rate == dec("0.30")
        assert rows[-1].bracket_to is None
        assert rows[-1].income_taxed == dec("10000")


# ---------------------------------------------------------------------------
# Preferential bracket breakdown
# ---------------------------------------------------------------------------


class TestPreferentialBreakdown:
    def test_stacks_on_top_of_ordinary_income(self):
        # ordinary 5,000 -> 0% room 35,000; remaining 15,000 at 15%
        rows = _build_preferential_breakdown(dec("5000"), dec("50000"), _PREFERENTIAL)
        assert [(r.rate, r.income_taxed, r.tax_amount) for r in rows] == [
            (dec("0.00"), dec("35000"), dec("0")),
            (dec("0.15"), dec("15000"), dec("2250")),
        ]

    def test_skips_bracket_filled_by_ordinary_income(self):
        rows = _build_preferential_breakdown(dec("45000"), dec("10000"), _PREFERENTIAL)
        assert [(r.rate, r.income_taxed, r.tax_amount) for r in rows] == [
            (dec("0.15"), dec("10000"), dec("1500")),
        ]

    def test_zero_preferential_returns_single_zero_row(self):
        rows = _build_preferential_breakdown(dec("5000"), dec("0"), _PREFERENTIAL)
        assert len(rows) == 1
        assert rows[0].income_taxed == dec("0")


# ---------------------------------------------------------------------------
# calculate_tax_detail — composition of the services
# ---------------------------------------------------------------------------


def _federal(total="100"):
    return FederalTaxResult(
        ordinary_income_tax=dec(total),
        preferential_income_tax=dec("0"),
        total_tax=dec(total),
        effective_rate=dec("0.01"),
        marginal_bracket_rate=dec("0.10"),
        bracket_breakdown=[],
    )


def _ohio(tax="50"):
    return OhioTaxResult(
        ohio_agi=dec("19700"),
        personal_exemption=dec("2000"),
        medical_deduction=dec("0"),
        ohio_tax_base=dec("17700"),
        tax_before_credits=dec(tax),
        retirement_income_credit=dec("0"),
        ohio_tax=dec(tax),
        effective_rate=dec("0.0025"),
    )


_INCOME = dict(
    pension=dec("10000"),
    interest=dec("1000"),
    ordinary_dividends=dec("500"),
    qualified_dividends=dec("700"),
    ira_distributions=dec("2000"),
    other_investment_ordinary=dec("300"),
    ss_benefit=dec("5000"),
    fixed_ltcg=dec("800"),
    tax_exempt_interest=dec("0"),
    wages=dec("4000"),
    above_the_line_adjustments=dec("600"),
    additional_deductions=dec("0"),
    filing_status="single",
    tax_year=2026,
)


class _Mocks:
    def __enter__(self):
        self.patchers = {
            "load": patch("services.tax_detail.load_federal_data", return_value=_FEDERAL_DATA),
            "ss": patch(
                "services.tax_detail.calculate_social_security_taxability",
                return_value=SocialSecurityResult(
                    dec("0"), dec("1000"), dec("0.2"), "fifty_percent"
                ),
            ),
            "fed": patch("services.tax_detail.calculate_federal_tax", return_value=_federal()),
            "niit": patch(
                "services.tax_detail.calculate_niit",
                return_value=NIITResult(dec("20"), dec("3300"), dec("200000"), dec("0.038")),
            ),
            "ohio": patch("services.tax_detail.calculate_ohio_tax", return_value=_ohio()),
        }
        self.m = {k: p.start() for k, p in self.patchers.items()}
        return self.m

    def __exit__(self, *exc):
        for p in self.patchers.values():
            p.stop()


class TestCalculateTaxDetail:
    def test_social_security_receives_agi_excluding_ss(self):
        # gross ordinary 17,800 + preferential 1,500 - adjustments 600
        with _Mocks() as m:
            calculate_tax_detail(**_INCOME, include_ohio=False)
        kwargs = m["ss"].call_args.kwargs
        assert kwargs["agi_excluding_ss"] == dec("18700")
        assert kwargs["ss_benefit"] == dec("5000")

    def test_federal_receives_split_taxable_income(self):
        # total ordinary 17,800 + 1,000 SS - 600 = 18,200; deduction 16,000
        with _Mocks() as m:
            calculate_tax_detail(**_INCOME, include_ohio=False)
        kwargs = m["fed"].call_args.kwargs
        assert kwargs["ordinary_income"] == dec("2200")
        assert kwargs["preferential_income"] == dec("1500")

    def test_unused_deduction_reduces_preferential_income(self):
        income = {**_INCOME, "pension": dec("0"), "wages": dec("0"), "ss_benefit": dec("0")}
        with _Mocks() as m:
            m["ss"].return_value = SocialSecurityResult(dec("0"), dec("0"), dec("0"), "none")
            result = calculate_tax_detail(**income, include_ohio=False)
        assert result.income.taxable_ordinary == dec("0")
        assert result.income.taxable_preferential == dec("0")

    def test_niit_receives_magi_and_net_investment_income(self):
        # MAGI = 18,200 ordinary + 1,500 preferential; NII = 1000+500+300+700+800
        with _Mocks() as m:
            calculate_tax_detail(**_INCOME, include_ohio=False)
        kwargs = m["niit"].call_args.kwargs
        assert kwargs["magi"] == dec("19700")
        assert kwargs["net_investment_income"] == dec("3300")

    def test_pension_and_ira_excluded_from_net_investment_income(self):
        income = {**_INCOME, "interest": dec("0"), "ordinary_dividends": dec("0")}
        income.update(other_investment_ordinary=dec("0"), qualified_dividends=dec("0"))
        income.update(fixed_ltcg=dec("0"))
        with _Mocks() as m:
            calculate_tax_detail(**income, include_ohio=False)
        assert m["niit"].call_args.kwargs["net_investment_income"] == dec("0")

    def test_ohio_not_calculated_when_excluded(self):
        with _Mocks() as m:
            result = calculate_tax_detail(**_INCOME, include_ohio=False)
        m["ohio"].assert_not_called()
        assert result.ohio is None
        assert result.total_ohio_tax == dec("0")

    def test_ohio_receives_federal_agi_and_ss_taxable(self):
        with _Mocks() as m:
            calculate_tax_detail(
                **_INCOME,
                include_ohio=True,
                gross_medical_expenses=dec("700"),
                ohio_qualifying_retirement_income=dec("1200"),
            )
        kwargs = m["ohio"].call_args.kwargs
        assert kwargs["federal_agi"] == dec("19700")
        assert kwargs["ss_taxable_federal"] == dec("1000")
        assert kwargs["gross_medical_expenses"] == dec("700")
        assert kwargs["qualifying_retirement_income"] == dec("1200")

    def test_totals_combine_federal_niit_and_ohio(self):
        with _Mocks():
            result = calculate_tax_detail(**_INCOME, include_ohio=True)
        assert result.total_niit == dec("20")
        assert result.total_federal_tax == dec("120")
        assert result.total_ohio_tax == dec("50")
        assert result.total_tax == dec("170")

    def test_overall_effective_rate_is_total_tax_over_agi(self):
        with _Mocks():
            result = calculate_tax_detail(**_INCOME, include_ohio=True)
        assert result.overall_effective_rate == dec("0.0086")  # 170 / 19,700

    def test_overall_effective_rate_zero_when_no_income(self):
        zero = {k: (dec("0") if isinstance(v, Decimal) else v) for k, v in _INCOME.items()}
        with _Mocks() as m:
            m["ss"].return_value = SocialSecurityResult(dec("0"), dec("0"), dec("0"), "none")
            result = calculate_tax_detail(**zero, include_ohio=False)
        assert result.overall_effective_rate == dec("0")

    def test_income_summary_reports_deductions_and_agi(self):
        with _Mocks():
            result = calculate_tax_detail(**_INCOME, include_ohio=False)
        assert result.income.gross_ordinary_income == dec("17800")
        assert result.income.ss_taxable == dec("1000")
        assert result.income.agi == dec("19700")
        assert result.income.standard_deduction == dec("16000")

    def test_unsupported_filing_status_propagates_value_error(self):
        with _Mocks() as m:
            m["ss"].side_effect = ValueError("Unsupported filing status: 'mfs'")
            with pytest.raises(ValueError):
                calculate_tax_detail(**{**_INCOME, "filing_status": "mfs"}, include_ohio=False)
