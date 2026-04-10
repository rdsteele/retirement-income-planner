"""EMR route — thin wrapper around calculate_emr service."""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from api.models.emr import (
    EMRComponents,
    EMRPoints,
    EMRRequest,
    EMRResponse,
    PlanningSignals,
)
from services.emr import EMRResult, SweepMode, calculate_emr
from services.emr import compute_planning_signals as _compute_service_signals

logger = logging.getLogger(__name__)

router = APIRouter()

_D = Decimal


def _to_decimal(value: float) -> Decimal:
    return _D(str(value))


def _to_decimal_or_none(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return _D(str(value))


def _build_points(result: EMRResult) -> EMRPoints:
    pts = result.points
    return EMRPoints(
        income=[float(p.income) for p in pts],
        total_tax=[float(p.total_tax) for p in pts],
        emr=[round(float(p.emr), 4) for p in pts],
        components=EMRComponents(
            ordinary=[round(float(p.emr_ordinary), 4) for p in pts],
            ss_torpedo=[round(float(p.emr_ss_torpedo), 4) for p in pts],
            pref_stacking=[round(float(p.emr_pref_stacking), 4) for p in pts],
            niit=[round(float(p.emr_niit), 4) for p in pts],
            ohio=[round(float(p.emr_ohio), 4) for p in pts],
        ),
        ss_taxable=[float(p.ss_taxable) for p in pts],
        ss_inclusion_rate=[round(float(p.ss_inclusion_rate), 4) for p in pts],
        taxable_ordinary=[float(p.taxable_ordinary) for p in pts],
        ohio_tax=[float(p.ohio_tax) for p in pts],
    )


def _to_float_or_none(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _compute_planning_signals(result: EMRResult, request: EMRRequest) -> PlanningSignals:
    signals = _compute_service_signals(
        result,
        fixed_ordinary=_to_decimal(
            request.pension
            + request.interest
            + request.ordinary_dividends
            + request.ira_distributions,
        ),
        variable_ordinary=_to_decimal(request.variable_ordinary),
        qualified_dividends=_to_decimal(request.qualified_dividends),
        fixed_ltcg=_to_decimal(request.fixed_ltcg),
        above_the_line_adjustments=_to_decimal(request.above_the_line_adjustments),
        additional_deductions=_to_decimal(request.additional_deductions),
    )
    return PlanningSignals(
        zero_ordinary_space=_to_float_or_none(signals.zero_ordinary_space),
        ltcg_0pct_remaining=_to_float_or_none(signals.ltcg_0pct_remaining),
        ltcg_0pct_ordinary_runway=_to_float_or_none(signals.ltcg_0pct_ordinary_runway),
        torpedo_active=signals.torpedo_active,
        ss_fully_taxable=signals.ss_fully_taxable,
        distance_to_22pct=_to_float_or_none(signals.distance_to_22pct),
        distance_to_24pct=_to_float_or_none(signals.distance_to_24pct),
    )


@router.post("/emr", response_model=EMRResponse)
def post_emr(request: EMRRequest):
    try:
        mode = SweepMode(request.sweep_mode)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sweep_mode: {request.sweep_mode!r}. "
            f"Must be 'ordinary' or 'preferential'.",
        )

    try:
        result = calculate_emr(
            pension=_to_decimal(request.pension),
            interest=_to_decimal(request.interest),
            ordinary_dividends=_to_decimal(request.ordinary_dividends),
            ira_distributions=_to_decimal(request.ira_distributions),
            ss_benefit=_to_decimal(request.ss_benefit),
            qualified_dividends=_to_decimal(request.qualified_dividends),
            fixed_ltcg=_to_decimal(request.fixed_ltcg),
            tax_exempt_interest=_to_decimal(request.tax_exempt_interest),
            sweep_mode=mode,
            filing_status=request.filing_status,
            tax_year=request.tax_year,
            variable_ordinary=_to_decimal(request.variable_ordinary),
            sweep_floor=_to_decimal(request.sweep_floor),
            sweep_ceiling=_to_decimal_or_none(request.sweep_ceiling),
            sweep_step=_to_decimal(request.sweep_step),
            include_ohio=request.include_ohio,
            ohio_medical_deduction=_to_decimal(request.ohio_medical_deduction),
            ohio_qualifying_retirement_income=_to_decimal(
                request.ohio_qualifying_retirement_income
            ),
            above_the_line_adjustments=_to_decimal(request.above_the_line_adjustments),
            additional_deductions=_to_decimal(request.additional_deductions),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error in EMR calculation")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        )

    return EMRResponse(
        sweep_mode=result.sweep_mode.value,
        filing_status=result.filing_status,
        tax_year=result.tax_year,
        points=_build_points(result),
        irmaa_thresholds=[float(t) for t in result.irmaa_thresholds],
        planning_signals=_compute_planning_signals(result, request),
    )
