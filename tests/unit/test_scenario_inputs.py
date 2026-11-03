"""Unit tests for services/scenario_inputs.py.

Turns a saved scenario (the JSON the planning pages store) into the assembled
income inputs for the EMR and Tax pages. Pure function: no file I/O.
"""

from decimal import Decimal

from services.income_inputs import IncomeInputs
from services.scenario_inputs import sweep_inputs_from_scenario


def dec(s: str) -> Decimal:
    return Decimal(s)


_ZERO = dec("0")


def _scenario(inputs=None, **income_planning):
    return {"inputs": inputs or {}, "income_planning": income_planning}


class TestEmptyAndMissing:
    def test_empty_scenario_is_all_zeros(self):
        assert sweep_inputs_from_scenario({}) == IncomeInputs()

    def test_returns_income_inputs(self):
        assert isinstance(sweep_inputs_from_scenario({}), IncomeInputs)

    def test_null_and_missing_values_are_zero(self):
        result = sweep_inputs_from_scenario(
            {"inputs": {"interest": None}, "income_planning": {"withdrawals": None}}
        )
        assert result.interest == _ZERO
        assert result.fixed_ltcg == _ZERO


class TestForcedIncomePassThrough:
    def test_forced_inputs_are_passed_through(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                {
                    "pension_taxable": 1600,
                    "wages": 5000,
                    "interest": 40,
                    "ordinary_dividends": 1410,
                    "qualified_dividends": 2500,
                    "ira_distributions": 2680,
                    "other_investment_ordinary": 300,
                    "ss_benefit": 12000,
                    "fixed_ltcg": 9000,
                    "tax_exempt_interest": 75,
                    "above_the_line_adjustments": 5400,
                    "additional_deductions": 1000,
                }
            )
        )
        assert result.pension == dec("1600")
        assert result.wages == dec("5000")
        assert result.interest == dec("40")
        assert result.ordinary_dividends == dec("1410")
        assert result.qualified_dividends == dec("2500")
        assert result.ira_distributions == dec("2680")
        assert result.other_investment_ordinary == dec("300")
        assert result.ss_benefit == dec("12000")
        assert result.fixed_ltcg == dec("9000")
        assert result.tax_exempt_interest == dec("75")
        assert result.above_the_line_adjustments == dec("5400")
        assert result.additional_deductions == dec("1000")

    def test_gross_pension_is_not_used(self):
        result = sweep_inputs_from_scenario(_scenario({"pension": 6000, "pension_taxable": 1600}))
        assert result.pension == dec("1600")

    def test_decimal_amounts_are_exact(self):
        result = sweep_inputs_from_scenario(_scenario({"interest": 0.1, "fixed_ltcg": 0.2}))
        assert result.interest == dec("0.1")
        assert result.fixed_ltcg == dec("0.2")


class TestPlannedWithdrawals:
    def test_traditional_withdrawals_add_to_ira_distributions(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                {"ira_distributions": 1000},
                trad_withdrawals=[{"id": "a", "amount": 4000}, {"id": "b", "amount": 500}],
            )
        )
        assert result.ira_distributions == dec("5500")

    def test_taxable_lot_gain_adds_to_fixed_ltcg(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                {"fixed_ltcg": 100},
                withdrawals=[{"id": "h1", "amount": 10000, "basis": 6000}],
            )
        )
        assert result.fixed_ltcg == dec("4100")

    def test_taxable_lot_sold_at_a_loss_adds_no_gain(self):
        result = sweep_inputs_from_scenario(
            _scenario(withdrawals=[{"id": "h1", "amount": 5000, "basis": 8000}])
        )
        assert result.fixed_ltcg == _ZERO

    def test_roth_and_hsa_withdrawals_are_not_income(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                roth_withdrawals=[{"id": "r", "amount": 9000}],
                hsa_withdrawals=[{"id": "h", "amount": 700}],
            )
        )
        assert result.ira_distributions == _ZERO
        assert result.fixed_ltcg == _ZERO


class TestExecutedWithdrawals:
    def test_tax_deferred_adds_full_amount_to_ira_distributions(self):
        result = sweep_inputs_from_scenario(
            _scenario(executed_withdrawals=[{"type": "tax_deferred", "amount": 8000}])
        )
        assert result.ira_distributions == dec("8000")

    def test_short_term_gain_is_other_investment_income_not_ira(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                {"other_investment_ordinary": 300},
                executed_withdrawals=[{"type": "stcg", "amount": 70000, "basis": 10000}],
            )
        )
        assert result.other_investment_ordinary == dec("60300")
        assert result.ira_distributions == _ZERO

    def test_long_term_gain_adds_to_fixed_ltcg(self):
        result = sweep_inputs_from_scenario(
            _scenario(executed_withdrawals=[{"type": "ltcg", "amount": 10000, "basis": 7000}])
        )
        assert result.fixed_ltcg == dec("3000")

    def test_gain_never_goes_negative(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                executed_withdrawals=[
                    {"type": "stcg", "amount": 100, "basis": 500},
                    {"type": "ltcg", "amount": 100, "basis": 500},
                ]
            )
        )
        assert result.other_investment_ordinary == _ZERO
        assert result.fixed_ltcg == _ZERO

    def test_tax_free_and_unknown_types_are_ignored(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                executed_withdrawals=[
                    {"type": "tax_free_roth", "amount": 5000},
                    {"type": "tax_free_hsa", "amount": 600},
                    {"type": "mystery", "amount": 123},
                ]
            )
        )
        assert result.ira_distributions == _ZERO
        assert result.other_investment_ordinary == _ZERO
        assert result.fixed_ltcg == _ZERO


class TestCombinedScenario:
    def test_all_sources_combine(self):
        result = sweep_inputs_from_scenario(
            _scenario(
                {"ira_distributions": 2000, "fixed_ltcg": 1000, "other_investment_ordinary": 500},
                trad_withdrawals=[{"amount": 10000}],
                withdrawals=[{"amount": 8000, "basis": 3000}],
                executed_withdrawals=[
                    {"type": "tax_deferred", "amount": 4000},
                    {"type": "stcg", "amount": 5000, "basis": 2000},
                    {"type": "ltcg", "amount": 6000, "basis": 4000},
                ],
            )
        )
        assert result.ira_distributions == dec("16000")  # 2000 + 10000 + 4000
        assert result.other_investment_ordinary == dec("3500")  # 500 + 3000
        assert result.fixed_ltcg == dec("8000")  # 1000 + 5000 + 2000
