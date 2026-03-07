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

logger = logging.getLogger(__name__)

router = APIRouter()

_D = Decimal
_ZERO = 0.0
_INCLUSION_85 = 0.85
_EMR_22 = 0.22
_EMR_24 = 0.24


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


def _compute_planning_signals(result: EMRResult) -> PlanningSignals:
    pts = result.points
    floor_income = float(pts[0].income) if pts else _ZERO

    # ltcg_0pct_remaining: first point where emr_pref_stacking > 0
    ltcg_0pct_remaining = None
    for p in pts:
        if float(p.emr_pref_stacking) > _ZERO:
            ltcg_0pct_remaining = float(p.income) - floor_income
            break

    # torpedo_active
    torpedo_active = any(float(p.emr_ss_torpedo) > _ZERO for p in pts)

    # ss_fully_taxable: check first point
    ss_fully_taxable = (
        float(pts[0].ss_inclusion_rate) >= _INCLUSION_85 if pts else False
    )

    # distance_to_22pct and 24pct: first point where emr_ordinary >= threshold
    distance_to_22pct = None
    distance_to_24pct = None
    if pts:
        first_ordinary = float(pts[0].emr_ordinary)
        if first_ordinary < _EMR_22:
            for p in pts:
                if float(p.emr_ordinary) >= _EMR_22:
                    distance_to_22pct = float(p.income) - floor_income
                    break
        if first_ordinary < _EMR_24:
            for p in pts:
                if float(p.emr_ordinary) >= _EMR_24:
                    distance_to_24pct = float(p.income) - floor_income
                    break

    return PlanningSignals(
        ltcg_0pct_remaining=ltcg_0pct_remaining,
        torpedo_active=torpedo_active,
        ss_fully_taxable=ss_fully_taxable,
        distance_to_22pct=distance_to_22pct,
        distance_to_24pct=distance_to_24pct,
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
            inherited_ira_rmd=_to_decimal(request.inherited_ira_rmd),
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
                request.ohio_qualifying_retirement_income),
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
        planning_signals=_compute_planning_signals(result),
    )
