"""Income plan routes — thin wrappers around income_plan and total_cost services."""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from api.models.income_plan import IncomePlanRequest, PlanSummaryResponse
from api.models.total_cost import TotalCostResponse
from api.routers.total_cost import (
    _build_points,
    _compute_planning_signals,
    _default_sweep_ceiling_fields,
    _to_decimal_or_none,
)
from services.emr import SweepMode
from services.income_plan import (
    ExecutedWithdrawal,
    PlannedWithdrawal,
    assemble_sweep_inputs,
    compute_plan_summary,
)
from services.total_cost import calculate_total_cost

logger = logging.getLogger(__name__)

router = APIRouter()

_D = Decimal


def _to_planned(items: list) -> list[PlannedWithdrawal]:
    return [
        PlannedWithdrawal(
            account_type=w.account_type,
            amount=_D(str(w.amount)),
            basis=_D(str(w.basis)),
        )
        for w in items
    ]


def _to_executed(items: list) -> list[ExecutedWithdrawal]:
    return [
        ExecutedWithdrawal(
            withdrawal_type=w.withdrawal_type,
            amount=_D(str(w.amount)),
            basis=_D(str(w.basis)),
        )
        for w in items
    ]


@router.post("/income-plan/summary", response_model=PlanSummaryResponse)
def post_income_plan_summary(request: IncomePlanRequest):
    """Compute a live plan summary without running the full EMR sweep.

    Called on every blur event in income.html to update the Plan Summary card.
    """
    planned = _to_planned(request.planned_withdrawals)
    executed = _to_executed(request.executed_withdrawals)

    try:
        summary = compute_plan_summary(
            filing_status=request.filing_status,
            gross_pension=_D(str(request.pension)),
            income=request.to_income_inputs(),
            essential_spending=_D(str(request.essential_spending)),
            discretionary_spending=_D(str(request.discretionary_spending)),
            aca_cliff_magi=_D(str(request.aca_cliff_magi)),
            estimated_taxes=_D(str(request.estimated_taxes)),
            planned=planned,
            executed=executed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return PlanSummaryResponse(
        magi=float(summary.magi),
        forced_ordinary=float(summary.forced_ordinary),
        forced_preferential=float(summary.forced_preferential),
        withdrawal_ordinary=float(summary.withdrawal_ordinary),
        withdrawal_preferential=float(summary.withdrawal_preferential),
        executed_ordinary=float(summary.executed_ordinary),
        executed_preferential=float(summary.executed_preferential),
        ss_taxable=float(summary.ss_taxable),
        provisional_income=float(summary.provisional_income),
        total_spending=float(summary.total_spending),
        total_income=float(summary.total_income),
        shortfall=float(summary.shortfall) if summary.shortfall is not None else None,
        aca_distance=float(summary.aca_distance) if summary.aca_distance is not None else None,
        aca_cliff_magi=float(summary.aca_cliff_magi),
        total_taxable_withdrawals=float(summary.total_taxable_withdrawals),
        total_traditional_withdrawals=float(summary.total_traditional_withdrawals),
        total_roth_withdrawals=float(summary.total_roth_withdrawals),
        total_hsa_withdrawals=float(summary.total_hsa_withdrawals),
        total_pension_annuity=float(summary.total_pension_annuity),
        total_wages=float(summary.total_wages),
        total_ss_benefit=float(summary.total_ss_benefit),
        total_all_withdrawals=float(summary.total_all_withdrawals),
    )


@router.post("/income-plan/calculate", response_model=TotalCostResponse)
def post_income_plan_calculate(request: IncomePlanRequest):
    """Run the full EMR sweep for an income plan.

    Assembles augmented sweep inputs (merging withdrawal totals into the
    forced-income fields) then delegates to calculate_total_cost. Replaces
    the payload-assembly logic that previously lived in income.html JavaScript.
    """
    mode = SweepMode("ordinary")
    planned = _to_planned(request.planned_withdrawals)
    executed = _to_executed(request.executed_withdrawals)

    income = assemble_sweep_inputs(
        income=request.to_income_inputs(), planned=planned, executed=executed
    )

    try:
        result = calculate_total_cost(
            income=income,
            sweep_mode=mode,
            variable_ordinary=_D("0"),
            filing_status=request.filing_status,
            tax_year=request.tax_year,
            sweep_floor=_D(str(request.sweep_floor)),
            sweep_ceiling=_to_decimal_or_none(request.sweep_ceiling),
            sweep_step=_to_decimal_or_none(request.sweep_step),
            include_ohio=request.include_ohio,
            ohio_medical_deduction=_D(str(request.ohio_medical_deduction)),
            ohio_qualifying_retirement_income=_D(str(request.ohio_qualifying_retirement_income)),
            include_aca=request.include_aca,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error in income plan calculation")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        )

    return TotalCostResponse(
        sweep_mode=mode.value,
        filing_status=request.filing_status,
        tax_year=request.tax_year,
        points=_build_points(result),
        irmaa_thresholds=[float(t) for t in result.irmaa_thresholds],
        **_default_sweep_ceiling_fields(request.filing_status, request.tax_year),
        aca_cliff_magi=float(result.aca_cliff_magi),
        aptc_annual_max=float(result.aptc_annual_max),
        cliff_sweep_value=float(result.cliff_sweep_value),
        planning_signals=_compute_planning_signals(
            result, income, _D("0"), request.include_aca, mode
        ),
    )
