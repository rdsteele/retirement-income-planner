"""Unit tests for services.aged_deduction: data and config lookups are replaced."""

from decimal import Decimal

import pytest

import services.aged_deduction as module
from services.income_inputs import IncomeInputs

D = Decimal
_FILERS = {"single": 1, "mfj": 2}
_AMOUNTS = {"single": "2000", "mfj": "1600"}


@pytest.fixture(autouse=True)
def _stub_data(monkeypatch):
    monkeypatch.setattr(module, "filer_count", lambda status: _FILERS[status])
    monkeypatch.setattr(
        module,
        "load_aged_deduction_data",
        lambda year: {"additional_standard_deduction": _AMOUNTS},
    )


def _income(taxpayer=False, spouse=False) -> IncomeInputs:
    return IncomeInputs(taxpayer_65_plus=taxpayer, spouse_65_plus=spouse)


class TestAgedFilerCount:
    def test_nobody_marked(self):
        assert module.aged_filer_count(_income(), "mfj") == 0

    def test_taxpayer_only(self):
        assert module.aged_filer_count(_income(taxpayer=True), "mfj") == 1

    def test_both_spouses_on_a_joint_return(self):
        assert module.aged_filer_count(_income(True, True), "mfj") == 2

    def test_spouse_flag_is_ignored_on_a_single_return(self):
        assert module.aged_filer_count(_income(True, True), "single") == 1
        assert module.aged_filer_count(_income(spouse=True), "single") == 0


class TestAdditionalStandardDeduction:
    def test_zero_without_loading_data(self, monkeypatch):
        def fail(year):
            raise AssertionError("data should not load when nobody is 65 or older")

        monkeypatch.setattr(module, "load_aged_deduction_data", fail)
        assert module.additional_standard_deduction(_income(), "single", 2099) == D("0")

    def test_single_uses_the_unmarried_amount(self):
        assert module.additional_standard_deduction(_income(True), "single", 2026) == D("2000")

    def test_joint_amount_is_per_person(self):
        assert module.additional_standard_deduction(_income(True), "mfj", 2026) == D("1600")
        assert module.additional_standard_deduction(_income(True, True), "mfj", 2026) == D("3200")

    def test_missing_year_data_is_an_error_when_someone_is_marked(self, monkeypatch):
        def missing(year):
            raise ValueError("no data")

        monkeypatch.setattr(module, "load_aged_deduction_data", missing)
        with pytest.raises(ValueError):
            module.additional_standard_deduction(_income(True), "single", 2099)
