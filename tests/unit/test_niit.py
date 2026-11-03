"""Unit tests for services/niit.py.

Pure calculation tests use literal thresholds; the data-loading wrapper is
tested with the data loader mocked (no file I/O).
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from services.niit import calculate_niit, compute_niit


def dec(s: str) -> Decimal:
    return Decimal(s)


_THRESHOLD = dec("200000")
_RATE = dec("0.038")


class TestComputeNiit:
    def test_magi_below_threshold_is_zero(self):
        assert compute_niit(dec("150000"), dec("50000"), _THRESHOLD, _RATE) == dec("0")

    def test_magi_at_threshold_is_zero(self):
        assert compute_niit(dec("200000"), dec("50000"), _THRESHOLD, _RATE) == dec("0")

    def test_zero_net_investment_income_is_zero(self):
        assert compute_niit(dec("300000"), dec("0"), _THRESHOLD, _RATE) == dec("0")

    def test_taxed_on_excess_magi_when_less_than_nii(self):
        # excess 10,000 < NII 60,000 -> 10,000 x 3.8% = 380
        assert compute_niit(dec("210000"), dec("60000"), _THRESHOLD, _RATE) == dec("380")

    def test_taxed_on_nii_when_less_than_excess(self):
        # NII 30,000 < excess 50,000 -> 30,000 x 3.8% = 1,140
        assert compute_niit(dec("250000"), dec("30000"), _THRESHOLD, _RATE) == dec("1140")

    def test_rounds_half_up_to_whole_dollar(self):
        # base 14 x 3.8% = 0.532 -> 1
        assert compute_niit(dec("200014"), dec("100"), _THRESHOLD, _RATE) == dec("1")


class TestCalculateNiit:
    _FEDERAL = {"niit": {"rate": "0.038", "single": "200000", "mfj": "250000"}}

    def _calc(self, magi, nii, status="single"):
        with patch("services.niit.load_federal_data", return_value=self._FEDERAL):
            return calculate_niit(dec(magi), dec(nii), status, 2026)

    def test_single_uses_single_threshold(self):
        r = self._calc("210000", "60000")
        assert r.niit == dec("380")
        assert r.threshold == dec("200000")

    def test_mfj_uses_mfj_threshold(self):
        r = self._calc("260000", "20000", "mfj")
        assert r.niit == dec("380")
        assert r.threshold == dec("250000")

    def test_reports_net_investment_income(self):
        assert self._calc("210000", "60000").net_investment_income == dec("60000")

    def test_below_threshold_reports_zero_tax(self):
        assert self._calc("100000", "60000").niit == dec("0")

    def test_unsupported_filing_status_raises(self):
        with pytest.raises(ValueError):
            self._calc("210000", "60000", "mfs")


class TestSumNetInvestmentIncome:
    def test_counts_investment_income_only(self):
        from services.niit import sum_net_investment_income

        total = sum_net_investment_income(
            interest=dec("100"),
            ordinary_dividends=dec("200"),
            other_investment_ordinary=dec("300"),
            qualified_dividends=dec("400"),
            fixed_ltcg=dec("500"),
        )
        assert total == dec("1500")
