"""Target points routes — thin wrappers around calculate_target_points."""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from api.models.target_points import (
    SweepTargetPointsRequest,
    TargetLegResponse,
    TargetPointsRequest,
    TargetPointsResponse,
)
from api.routers.income_plan import _to_executed, _to_planned
from api.routers.total_cost import _to_decimal_or_none
from services.emr import SweepMode
from services.income_inputs import IncomeInputs
from services.income_plan import assemble_sweep_inputs
from services.target_points import TargetLeg, calculate_target_points

logger = logging.getLogger(__name__)

router = APIRouter()

_D = Decimal


def _to_leg_response(leg: TargetLeg) -> TargetLegResponse:
    return TargetLegResponse(
        from_income=float(leg.from_income),
        to_income=float(leg.to_income),
        average_emr=float(leg.average_emr),
        cost=float(leg.cost),
        causes=list(leg.causes),
    )


def _parse_sweep_mode(value: str) -> SweepMode:
    try:
        return SweepMode(value)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sweep_mode: {value!r}. Must be 'ordinary' or 'preferential'.",
        )


def _respond(
    request: TargetPointsRequest | SweepTargetPointsRequest,
    *,
    income: IncomeInputs,
    mode: SweepMode,
    variable_ordinary: Decimal,
) -> TargetPointsResponse:
    """Run the search for either request shape and build the response."""
    try:
        result = calculate_target_points(
            income=income,
            filing_status=request.filing_status,
            tax_year=request.tax_year,
            max_rate=_D(str(request.max_emr)),
            sweep_mode=mode,
            variable_ordinary=variable_ordinary,
            sweep_floor=_D(str(request.sweep_floor)),
            sweep_ceiling=_to_decimal_or_none(request.sweep_ceiling),
            sweep_step=_to_decimal_or_none(request.sweep_step),
            include_ohio=request.include_ohio,
            ohio_medical_deduction=_D(str(request.ohio_medical_deduction)),
            ohio_qualifying_retirement_income=_D(str(request.ohio_qualifying_retirement_income)),
            include_aca=request.include_aca,
            include_irmaa=request.include_irmaa,
            irmaa_enrollees=request.irmaa_enrollees,
            irmaa_inflation_rate=_to_decimal_or_none(request.irmaa_inflation_rate),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error in target points calculation")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        )

    return TargetPointsResponse(
        filing_status=request.filing_status,
        tax_year=request.tax_year,
        max_emr=request.max_emr,
        targets=[float(t) for t in result.targets],
        legs=[_to_leg_response(leg) for leg in result.legs],
        irmaa_thresholds=[float(t) for t in result.irmaa_thresholds],
    )


@router.post("/target-points", response_model=TargetPointsResponse)
def post_target_points(request: TargetPointsRequest):
    """Find the target income points and desirable legs for an income plan."""
    income = assemble_sweep_inputs(
        income=request.to_income_inputs(),
        planned=_to_planned(request.planned_withdrawals),
        executed=_to_executed(request.executed_withdrawals),
    )
    return _respond(request, income=income, mode=SweepMode.ORDINARY, variable_ordinary=_D("0"))


@router.post("/total-cost/target-points", response_model=TargetPointsResponse)
def post_sweep_target_points(request: SweepTargetPointsRequest):
    """Find the target income points and desirable legs for a total cost sweep request."""
    return _respond(
        request,
        income=request.to_income_inputs(),
        mode=_parse_sweep_mode(request.sweep_mode),
        variable_ordinary=_D(str(request.variable_ordinary)),
    )
