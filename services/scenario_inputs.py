"""Scenario input assembly service.

Turns a saved scenario (the JSON the planning pages store) into the assembled income
inputs shown on the EMR and Tax pages: forced income plus planned and executed
withdrawals, classified into ordinary, investment, and preferential income. Composes
income_plan so every page uses the one classification. Pure function: no file I/O.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from services.income_plan import ExecutedWithdrawal, PlannedWithdrawal, assemble_sweep_inputs

_ZERO = Decimal("0")

# Planned withdrawal lists as stored in a scenario's income_planning section.
_PLANNED_LIST_BY_ACCOUNT_TYPE = {
    "traditional": "trad_withdrawals",
    "roth": "roth_withdrawals",
    "hsa": "hsa_withdrawals",
}


@dataclass
class ScenarioSweepInputs:
    pension: Decimal  # taxable portion only
    wages: Decimal
    interest: Decimal
    ordinary_dividends: Decimal
    qualified_dividends: Decimal
    ira_distributions: Decimal
    other_investment_ordinary: Decimal
    ss_benefit: Decimal
    fixed_ltcg: Decimal
    tax_exempt_interest: Decimal
    above_the_line_adjustments: Decimal
    additional_deductions: Decimal


def _money(value: object) -> Decimal:
    """Return a stored JSON number as a Decimal (missing or null is zero)."""
    if value is None:
        return _ZERO
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"Not a number: {value!r}") from None


def _planned_withdrawals(planning: dict) -> list[PlannedWithdrawal]:
    planned = [
        PlannedWithdrawal("taxable", _money(lot.get("amount")), _money(lot.get("basis")))
        for lot in planning.get("withdrawals") or []
    ]
    for account_type, key in _PLANNED_LIST_BY_ACCOUNT_TYPE.items():
        planned += [
            PlannedWithdrawal(account_type, _money(w.get("amount")))
            for w in planning.get(key) or []
        ]
    return planned


def _executed_withdrawals(planning: dict) -> list[ExecutedWithdrawal]:
    return [
        ExecutedWithdrawal(w.get("type") or "", _money(w.get("amount")), _money(w.get("basis")))
        for w in planning.get("executed_withdrawals") or []
    ]


def sweep_inputs_from_scenario(scenario: dict) -> ScenarioSweepInputs:
    inputs = scenario.get("inputs") or {}
    planning = scenario.get("income_planning") or {}
    assembled = assemble_sweep_inputs(
        pension_taxable=_money(inputs.get("pension_taxable")),
        interest=_money(inputs.get("interest")),
        ordinary_dividends=_money(inputs.get("ordinary_dividends")),
        ira_distributions=_money(inputs.get("ira_distributions")),
        ss_benefit=_money(inputs.get("ss_benefit")),
        qualified_dividends=_money(inputs.get("qualified_dividends")),
        fixed_ltcg=_money(inputs.get("fixed_ltcg")),
        above_the_line_adjustments=_money(inputs.get("above_the_line_adjustments")),
        tax_exempt_interest=_money(inputs.get("tax_exempt_interest")),
        planned=_planned_withdrawals(planning),
        executed=_executed_withdrawals(planning),
        other_investment_ordinary=_money(inputs.get("other_investment_ordinary")),
    )
    return ScenarioSweepInputs(
        pension=assembled["pension"],
        wages=_money(inputs.get("wages")),
        interest=assembled["interest"],
        ordinary_dividends=assembled["ordinary_dividends"],
        qualified_dividends=assembled["qualified_dividends"],
        ira_distributions=assembled["ira_distributions"],
        other_investment_ordinary=assembled["other_investment_ordinary"],
        ss_benefit=assembled["ss_benefit"],
        fixed_ltcg=assembled["fixed_ltcg"],
        tax_exempt_interest=assembled["tax_exempt_interest"],
        above_the_line_adjustments=assembled["above_the_line_adjustments"],
        additional_deductions=_money(inputs.get("additional_deductions")),
    )
