"""Unit tests for services.senior_deduction: the data file and filer count are replaced."""

from decimal import Decimal

import pytest

import services.senior_deduction as module
from services.income_inputs import IncomeInputs

D = Decimal
_DATA = {
    "first_year": 2025,
    "last_year": 2028,
    "amount_per_person": "6000",
    "phaseout_rate": "0.06",
    "phaseout_start": {"single": "75000", "mfj": "150000"},
}


@pytest.fixture(autouse=True)
def _stub_data(monkeypatch):
    monkeypatch.setattr(module, "load_senior_deduction_data", lambda: _DATA)


def _income(claim: bool = True) -> IncomeInputs:
    return IncomeInputs(claim_senior_deduction=claim)


def _with_count(monkeypatch, count: int) -> None:
    monkeypatch.setattr(module, "aged_filer_count", lambda income, status: count)


class TestAvailability:
    def test_years_come_from_the_data_file(self):
        assert module.senior_deduction_years() == (2025, 2028)

    @pytest.mark.parametrize(
        ("year", "expected"), [(2024, False), (2025, True), (2028, True), (2029, False)]
    )
    def test_available_only_inside_the_years(self, year, expected):
        assert module.senior_deduction_available(year) is expected


class TestSeniorDeduction:
    def test_zero_when_not_claimed(self, monkeypatch):
        _with_count(monkeypatch, 1)
        assert module.senior_deduction(_income(claim=False), "single", 2026, D("50000")) == D("0")

    def test_zero_when_nobody_is_65(self, monkeypatch):
        _with_count(monkeypatch, 0)
        assert module.senior_deduction(_income(), "single", 2026, D("50000")) == D("0")

    def test_zero_outside_the_years(self, monkeypatch):
        _with_count(monkeypatch, 1)
        assert module.senior_deduction(_income(), "single", 2029, D("50000")) == D("0")

    def test_full_amount_below_the_phaseout(self, monkeypatch):
        _with_count(monkeypatch, 1)
        assert module.senior_deduction(_income(), "single", 2026, D("75000")) == D("6000")

    def test_amount_is_per_person(self, monkeypatch):
        _with_count(monkeypatch, 2)
        assert module.senior_deduction(_income(), "mfj", 2026, D("100000")) == D("12000")

    def test_reduced_by_the_rate_over_the_threshold(self, monkeypatch):
        _with_count(monkeypatch, 1)
        # 6,000 - 6% x (100,000 - 75,000)
        assert module.senior_deduction(_income(), "single", 2026, D("100000")) == D("4500")

    def test_the_reduction_applies_to_each_persons_amount(self, monkeypatch):
        _with_count(monkeypatch, 2)
        # each person: 6,000 - 6% x (200,000 - 150,000) = 3,000
        assert module.senior_deduction(_income(), "mfj", 2026, D("200000")) == D("6000")
        # each person: 6,000 - 6% x (250,000 - 150,000) = 0
        assert module.senior_deduction(_income(), "mfj", 2026, D("250000")) == D("0")

    def test_never_negative(self, monkeypatch):
        _with_count(monkeypatch, 1)
        assert module.senior_deduction(_income(), "single", 2026, D("175000")) == D("0")
        assert module.senior_deduction(_income(), "single", 2026, D("900000")) == D("0")
