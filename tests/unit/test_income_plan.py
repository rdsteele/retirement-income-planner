"""Unit tests for services/income_plan.py.

Covers: classify_withdrawals, compute_plan_summary, assemble_sweep_inputs.
No file I/O, no server. SS taxability is tested via the real social_security
service (which loads data files), so these tests are not pure-unit — they
rely on the real SS threshold data. That is intentional: we want to verify
that compute_plan_summary uses the accurate service, not a JS approximation.
"""

from decimal import Decimal

from services.income_plan import (
    ExecutedWithdrawal,
    PlannedWithdrawal,
    assemble_sweep_inputs,
    classify_withdrawals,
    compute_plan_summary,
)


def d(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# classify_withdrawals
# ---------------------------------------------------------------------------

class TestClassifyWithdrawals:
    def test_empty(self):
        totals = classify_withdrawals([], [])
        assert totals.taxable_gains == d("0")
        assert totals.taxable_basis == d("0")
        assert totals.traditional == d("0")
        assert totals.roth == d("0")
        assert totals.hsa == d("0")
        assert totals.exec_ordinary == d("0")
        assert totals.exec_preferential == d("0")

    def test_taxable_holding_splits_gain_and_basis(self):
        planned = [PlannedWithdrawal(account_type="taxable", amount=d("10000"), basis=d("6000"))]
        totals = classify_withdrawals(planned, [])
        assert totals.taxable_gains == d("4000")
        assert totals.taxable_basis == d("6000")

    def test_taxable_holding_no_gain_when_basis_exceeds_amount(self):
        planned = [PlannedWithdrawal(account_type="taxable", amount=d("5000"), basis=d("8000"))]
        totals = classify_withdrawals(planned, [])
        assert totals.taxable_gains == d("0")
        assert totals.taxable_basis == d("5000")

    def test_traditional_is_ordinary(self):
        planned = [PlannedWithdrawal(account_type="traditional", amount=d("20000"))]
        totals = classify_withdrawals(planned, [])
        assert totals.traditional == d("20000")
        assert totals.taxable_gains == d("0")

    def test_roth_is_magi_neutral(self):
        planned = [PlannedWithdrawal(account_type="roth", amount=d("15000"))]
        totals = classify_withdrawals(planned, [])
        assert totals.roth == d("15000")
        assert totals.taxable_gains == d("0")
        assert totals.traditional == d("0")

    def test_hsa_is_magi_neutral(self):
        planned = [PlannedWithdrawal(account_type="hsa", amount=d("3000"))]
        totals = classify_withdrawals(planned, [])
        assert totals.hsa == d("3000")

    def test_executed_ltcg_is_preferential_gain_only(self):
        executed = [ExecutedWithdrawal(withdrawal_type="ltcg", amount=d("10000"), basis=d("7000"))]
        totals = classify_withdrawals([], executed)
        assert totals.exec_preferential == d("3000")
        assert totals.exec_ordinary == d("0")
        assert totals.exec_taxable_amount == d("10000")

    def test_executed_stcg_gain_is_ordinary(self):
        executed = [ExecutedWithdrawal(withdrawal_type="stcg", amount=d("5000"), basis=d("3000"))]
        totals = classify_withdrawals([], executed)
        assert totals.exec_ordinary == d("2000")
        assert totals.exec_preferential == d("0")
        assert totals.exec_taxable_amount == d("5000")

    def test_executed_tax_deferred_is_fully_ordinary(self):
        executed = [ExecutedWithdrawal(withdrawal_type="tax_deferred", amount=d("8000"), basis=d("0"))]
        totals = classify_withdrawals([], executed)
        assert totals.exec_ordinary == d("8000")
        assert totals.exec_traditional == d("8000")

    def test_executed_tax_free_roth_excluded_from_income(self):
        executed = [ExecutedWithdrawal(withdrawal_type="tax_free_roth", amount=d("5000"))]
        totals = classify_withdrawals([], executed)
        assert totals.exec_roth == d("5000")
        assert totals.exec_ordinary == d("0")
        assert totals.exec_preferential == d("0")

    def test_executed_tax_free_hsa_excluded_from_income(self):
        executed = [ExecutedWithdrawal(withdrawal_type="tax_free_hsa", amount=d("2000"))]
        totals = classify_withdrawals([], executed)
        assert totals.exec_hsa == d("2000")
        assert totals.exec_ordinary == d("0")

    def test_multiple_items_summed(self):
        planned = [
            PlannedWithdrawal(account_type="taxable", amount=d("10000"), basis=d("4000")),
            PlannedWithdrawal(account_type="traditional", amount=d("15000")),
        ]
        executed = [
            ExecutedWithdrawal(withdrawal_type="ltcg", amount=d("8000"), basis=d("5000")),
        ]
        totals = classify_withdrawals(planned, executed)
        assert totals.taxable_gains == d("6000")
        assert totals.taxable_basis == d("4000")
        assert totals.traditional == d("15000")
        assert totals.exec_preferential == d("3000")


# ---------------------------------------------------------------------------
# compute_plan_summary — basic MAGI and shortfall checks
# ---------------------------------------------------------------------------

def _base_summary(**overrides):
    """Build a minimal summary request with all defaults."""
    defaults = dict(
        filing_status="single",
        pension=d("0"),
        interest=d("0"),
        ordinary_dividends=d("0"),
        ira_distributions=d("0"),
        ss_benefit=d("0"),
        qualified_dividends=d("0"),
        fixed_ltcg=d("0"),
        above_the_line_adjustments=d("0"),
        tax_exempt_interest=d("0"),
        essential_spending=d("0"),
        discretionary_spending=d("0"),
        aca_cliff_magi=d("0"),
        estimated_taxes=d("0"),
        planned=[],
        executed=[],
    )
    defaults.update(overrides)
    return compute_plan_summary(**defaults)


class TestComputePlanSummaryBasic:
    def test_zero_inputs_yields_zero_magi(self):
        s = _base_summary()
        assert s.magi == d("0")

    def test_pension_is_ordinary_income(self):
        s = _base_summary(pension=d("30000"))
        assert s.magi == d("30000")
        assert s.forced_ordinary == d("30000")
        assert s.forced_preferential == d("0")

    def test_qualified_dividends_are_preferential(self):
        s = _base_summary(qualified_dividends=d("5000"))
        assert s.magi == d("5000")
        assert s.forced_preferential == d("5000")

    def test_above_the_line_adjustments_reduce_magi(self):
        s = _base_summary(pension=d("30000"), above_the_line_adjustments=d("5000"))
        assert s.magi == d("25000")

    def test_planned_traditional_adds_to_ordinary(self):
        s = _base_summary(
            planned=[PlannedWithdrawal(account_type="traditional", amount=d("20000"))]
        )
        assert s.magi == d("20000")
        assert s.withdrawal_ordinary == d("20000")

    def test_planned_roth_does_not_affect_magi(self):
        s = _base_summary(
            planned=[PlannedWithdrawal(account_type="roth", amount=d("10000"))]
        )
        assert s.magi == d("0")
        assert s.total_roth_withdrawals == d("10000")

    def test_planned_taxable_gain_is_preferential(self):
        s = _base_summary(
            planned=[PlannedWithdrawal(account_type="taxable", amount=d("10000"), basis=d("6000"))]
        )
        assert s.withdrawal_preferential == d("4000")
        assert s.magi == d("4000")

    def test_no_shortfall_when_no_spending(self):
        s = _base_summary(pension=d("50000"))
        assert s.shortfall is None

    def test_shortfall_when_expenses_exceed_income(self):
        s = _base_summary(
            pension=d("20000"),
            essential_spending=d("30000"),
        )
        assert s.shortfall is not None
        assert s.shortfall > d("0")

    def test_surplus_when_income_exceeds_expenses(self):
        s = _base_summary(
            pension=d("50000"),
            essential_spending=d("20000"),
        )
        assert s.shortfall is not None
        assert s.shortfall < d("0")

    def test_no_aca_distance_when_cliff_is_zero(self):
        s = _base_summary(pension=d("30000"), aca_cliff_magi=d("0"))
        assert s.aca_distance is None

    def test_aca_distance_computed_when_cliff_provided(self):
        s = _base_summary(pension=d("30000"), aca_cliff_magi=d("62600"))
        assert s.aca_distance == d("32600")

    def test_aca_distance_negative_when_over_cliff(self):
        s = _base_summary(pension=d("70000"), aca_cliff_magi=d("62600"))
        assert s.aca_distance is not None
        assert s.aca_distance < d("0")


class TestComputePlanSummarySSAccuracy:
    """Verify that the service uses the real SS taxability logic, not a JS approximation.

    The JS approximation was single-filer only. These tests confirm MFJ works
    correctly and that the real thresholds are applied.
    """

    def test_ss_below_threshold_no_taxable(self):
        # Single, PI = 25000 (at threshold) → taxable SS = 0
        s = _base_summary(
            filing_status="single",
            ss_benefit=d("20000"),
            pension=d("15000"),  # AGI excl SS = 15000; PI = 15000+10000 = 25000
        )
        assert s.ss_taxable == d("0")

    def test_ss_eighty_five_pct_fully_reached(self):
        # Single, high income → max 85% taxable
        s = _base_summary(
            filing_status="single",
            ss_benefit=d("20000"),
            pension=d("50000"),
        )
        assert s.ss_taxable == d("17000")  # 85% of 20000

    def test_mfj_uses_higher_threshold(self):
        # MFJ tier_1 = 32000; ss=24000, pension=20000 → PI=20000+12000=32000 → none
        s = _base_summary(
            filing_status="mfj",
            ss_benefit=d("24000"),
            pension=d("20000"),
        )
        assert s.ss_taxable == d("0")
        assert s.provisional_income == d("32000")

    def test_mfj_fifty_pct_tier(self):
        # MFJ, ss=24000, pension=25000 → PI=25000+12000=37000 → 50% tier
        s = _base_summary(
            filing_status="mfj",
            ss_benefit=d("24000"),
            pension=d("25000"),
        )
        assert s.ss_taxable == d("2500")


# ---------------------------------------------------------------------------
# assemble_sweep_inputs
# ---------------------------------------------------------------------------

class TestAssembleSweepInputs:
    def _base(self, **overrides):
        defaults = dict(
            pension=d("0"),
            interest=d("0"),
            ordinary_dividends=d("0"),
            ira_distributions=d("0"),
            ss_benefit=d("0"),
            qualified_dividends=d("0"),
            fixed_ltcg=d("0"),
            above_the_line_adjustments=d("0"),
            tax_exempt_interest=d("0"),
            planned=[],
            executed=[],
        )
        defaults.update(overrides)
        return assemble_sweep_inputs(**defaults)

    def test_no_withdrawals_passthrough(self):
        result = self._base(pension=d("30000"), ss_benefit=d("24000"))
        assert result["pension"] == d("30000")
        assert result["ss_benefit"] == d("24000")
        assert result["ira_distributions"] == d("0")
        assert result["fixed_ltcg"] == d("0")

    def test_traditional_added_to_ira_distributions(self):
        result = self._base(
            ira_distributions=d("10000"),
            planned=[PlannedWithdrawal(account_type="traditional", amount=d("20000"))],
        )
        assert result["ira_distributions"] == d("30000")

    def test_taxable_gains_added_to_fixed_ltcg(self):
        result = self._base(
            fixed_ltcg=d("5000"),
            planned=[PlannedWithdrawal(account_type="taxable", amount=d("10000"), basis=d("6000"))],
        )
        assert result["fixed_ltcg"] == d("9000")  # 5000 + 4000 gain

    def test_executed_ordinary_added_to_ira_distributions(self):
        result = self._base(
            executed=[ExecutedWithdrawal(withdrawal_type="tax_deferred", amount=d("8000"))],
        )
        assert result["ira_distributions"] == d("8000")

    def test_executed_ltcg_added_to_fixed_ltcg(self):
        result = self._base(
            executed=[ExecutedWithdrawal(withdrawal_type="ltcg", amount=d("10000"), basis=d("7000"))],
        )
        assert result["fixed_ltcg"] == d("3000")

    def test_roth_and_hsa_not_added_to_any_income(self):
        result = self._base(
            planned=[
                PlannedWithdrawal(account_type="roth", amount=d("10000")),
                PlannedWithdrawal(account_type="hsa", amount=d("2000")),
            ],
        )
        assert result["ira_distributions"] == d("0")
        assert result["fixed_ltcg"] == d("0")

    def test_all_income_fields_present_in_output(self):
        result = self._base()
        required = {
            "pension", "interest", "ordinary_dividends", "ira_distributions",
            "ss_benefit", "qualified_dividends", "fixed_ltcg",
            "above_the_line_adjustments", "tax_exempt_interest",
        }
        assert required.issubset(result.keys())

    def test_combined_scenario(self):
        result = self._base(
            ira_distributions=d("5000"),
            fixed_ltcg=d("2000"),
            planned=[
                PlannedWithdrawal(account_type="traditional", amount=d("10000")),
                PlannedWithdrawal(account_type="taxable", amount=d("8000"), basis=d("3000")),
            ],
            executed=[
                ExecutedWithdrawal(withdrawal_type="tax_deferred", amount=d("4000")),
                ExecutedWithdrawal(withdrawal_type="ltcg", amount=d("6000"), basis=d("4000")),
            ],
        )
        # ira_distributions = 5000 + 10000 (trad) + 4000 (exec tax_deferred) = 19000
        assert result["ira_distributions"] == d("19000")
        # fixed_ltcg = 2000 + 5000 (taxable gain) + 2000 (ltcg exec gain) = 9000
        assert result["fixed_ltcg"] == d("9000")
