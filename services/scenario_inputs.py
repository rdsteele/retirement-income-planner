"""Scenario input assembly service.

Turns a saved scenario (the JSON the planning pages store) into the assembled income
inputs shown on the EMR and Tax pages: forced income plus planned and executed
withdrawals, classified into ordinary, investment, and preferential income. Composes
income_plan so every page uses the one classification. Pure function: no file I/O.
"""

from services.income_inputs import IncomeInputs, to_decimal
from services.income_plan import ExecutedWithdrawal, PlannedWithdrawal, assemble_sweep_inputs

# Planned withdrawal lists as stored in a scenario's income_planning section.
_PLANNED_LIST_BY_ACCOUNT_TYPE = {
    "traditional": "trad_withdrawals",
    "roth": "roth_withdrawals",
    "hsa": "hsa_withdrawals",
}


def _planned_withdrawals(planning: dict) -> list[PlannedWithdrawal]:
    planned = [
        PlannedWithdrawal("taxable", to_decimal(lot.get("amount")), to_decimal(lot.get("basis")))
        for lot in planning.get("withdrawals") or []
    ]
    for account_type, key in _PLANNED_LIST_BY_ACCOUNT_TYPE.items():
        planned += [
            PlannedWithdrawal(account_type, to_decimal(w.get("amount")))
            for w in planning.get(key) or []
        ]
    return planned


def _executed_withdrawals(planning: dict) -> list[ExecutedWithdrawal]:
    return [
        ExecutedWithdrawal(
            w.get("type") or "", to_decimal(w.get("amount")), to_decimal(w.get("basis"))
        )
        for w in planning.get("executed_withdrawals") or []
    ]


def sweep_inputs_from_scenario(scenario: dict) -> IncomeInputs:
    """The scenario's income with planned and executed withdrawals folded in."""
    inputs = scenario.get("inputs") or {}
    planning = scenario.get("income_planning") or {}
    # a scenario stores the taxable pension as pension_taxable (pension is the gross payment)
    forced = IncomeInputs.from_numbers(inputs, pension=to_decimal(inputs.get("pension_taxable")))
    return assemble_sweep_inputs(
        income=forced,
        planned=_planned_withdrawals(planning),
        executed=_executed_withdrawals(planning),
    )
