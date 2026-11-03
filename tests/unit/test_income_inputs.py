"""Unit tests for services/income_inputs.py (no I/O)."""

import dataclasses
from decimal import Decimal

import pytest

from services.income_inputs import IncomeInputs


def dec(s: str) -> Decimal:
    return Decimal(s)


_ZERO = dec("0")


class TestDefaults:
    def test_every_field_defaults_to_zero(self):
        income = IncomeInputs()
        assert all(getattr(income, f.name) == _ZERO for f in dataclasses.fields(income))

    def test_is_immutable(self):
        income = IncomeInputs(pension=dec("1"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            income.pension = dec("2")

    def test_replace_returns_a_modified_copy(self):
        income = IncomeInputs(pension=dec("1"), interest=dec("2"))
        changed = dataclasses.replace(income, pension=dec("5"))
        assert (changed.pension, changed.interest, income.pension) == (dec("5"), dec("2"), dec("1"))


class TestDerivedAmounts:
    _income = IncomeInputs(
        pension=dec("100"),
        wages=dec("200"),
        interest=dec("3"),
        ordinary_dividends=dec("4"),
        qualified_dividends=dec("5"),
        ira_distributions=dec("600"),
        other_investment_ordinary=dec("7"),
        ss_benefit=dec("8000"),
        fixed_ltcg=dec("90"),
        tax_exempt_interest=dec("1000"),
        above_the_line_adjustments=dec("11"),
        additional_deductions=dec("12"),
    )

    def test_fixed_ordinary_is_all_ordinary_income_before_social_security(self):
        # pension + wages + interest + non-qualified dividends + IRA + other investment income
        assert self._income.fixed_ordinary == dec("914")

    def test_investment_ordinary_excludes_pension_wages_and_ira(self):
        assert self._income.investment_ordinary == dec("14")  # 3 + 4 + 7

    def test_fixed_preferential_is_qualified_dividends_plus_ltcg(self):
        assert self._income.fixed_preferential == dec("95")

    def test_net_investment_income_counts_investment_income_only(self):
        # interest 3 + non-qualified dividends 4 + other investment 7 + qualified 5 + LTCG 90
        # (pension, wages, and IRA distributions are not net investment income)
        assert self._income.net_investment_income == dec("109")

    def test_social_security_and_adjustments_are_not_in_the_sums(self):
        bare = IncomeInputs(ss_benefit=dec("5"), above_the_line_adjustments=dec("6"))
        assert (bare.fixed_ordinary, bare.fixed_preferential) == (_ZERO, _ZERO)


class TestFromNumbers:
    def test_builds_from_a_mapping_of_numbers(self):
        income = IncomeInputs.from_numbers({"pension": 1600, "interest": 40.5, "wages": "10"})
        assert (income.pension, income.interest, income.wages) == (
            dec("1600"),
            dec("40.5"),
            dec("10"),
        )

    def test_missing_and_null_values_are_zero(self):
        income = IncomeInputs.from_numbers({"interest": None})
        assert income.interest == _ZERO
        assert income.pension == _ZERO

    def test_floats_convert_exactly(self):
        assert IncomeInputs.from_numbers({"interest": 0.1}).interest == dec("0.1")

    def test_unknown_keys_are_ignored(self):
        assert IncomeInputs.from_numbers({"favorite_color": "blue"}) == IncomeInputs()

    def test_non_numeric_value_raises_value_error(self):
        with pytest.raises(ValueError, match="Not a number"):
            IncomeInputs.from_numbers({"interest": "abc"})

    def test_overrides_replace_mapping_values(self):
        income = IncomeInputs.from_numbers({"pension": 5, "interest": 9}, pension=dec("77"))
        assert (income.pension, income.interest) == (dec("77"), dec("9"))
