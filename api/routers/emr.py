"""EMR route — thin wrapper around calculate_emr service."""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from api.models.emr import (
    BracketDistance,
    EMRComponents,
    EMRPoints,
    EMRRequest,
    EMRResponse,
    PlanningSignals,
)
from services.data_loader import get_default_sweep_ceiling_bracket_rate
from services.emr import BracketDistance as ServiceBracketDistance
from services.emr import EMRResult, SweepMode, calculate_emr, get_default_sweep_ceiling
from services.emr import compute_planning_signals as _compute_service_signals
from services.income_inputs import IncomeInputs

logger = logging.getLogger(__name__)

router = APIRouter()

_D = Decimal


def _to_decimal(value: float) -> Decimal:
    return _D(str(value))


def _to_decimal_or_none(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return _D(str(value))


def _to_bracket_distance_responses(
    distances: list[ServiceBracketDistance],
) -> list[BracketDistance]:
    return [
        BracketDistance(
            rate=float(d.rate),
            distance=float(d.distance) if d.distance is not None else None,
        )
        for d in distances
    ]


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


def _compute_planning_signals(
    result: EMRResult, income: IncomeInputs, variable_ordinary: Decimal
) -> PlanningSignals:
    signals = _compute_service_signals(result, income=income, variable_ordinary=variable_ordinary)
    return PlanningSignals(
        zero_ordinary_space=_to_float_or_none(signals.zero_ordinary_space),
        ltcg_0pct_remaining=_to_float_or_none(signals.ltcg_0pct_remaining),
        ltcg_0pct_ordinary_runway=_to_float_or_none(signals.ltcg_0pct_ordinary_runway),
        torpedo_active=signals.torpedo_active,
        ss_fully_taxable=signals.ss_fully_taxable,
        bracket_distances=_to_bracket_distance_responses(signals.bracket_distances),
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

    income = request.to_income_inputs()
    variable_ordinary = _to_decimal(request.variable_ordinary)
    try:
        result = calculate_emr(
            income=income,
            sweep_mode=mode,
            filing_status=request.filing_status,
            tax_year=request.tax_year,
            variable_ordinary=variable_ordinary,
            sweep_floor=_to_decimal(request.sweep_floor),
            sweep_ceiling=_to_decimal_or_none(request.sweep_ceiling),
            sweep_step=_to_decimal_or_none(request.sweep_step),
            include_ohio=request.include_ohio,
            ohio_medical_deduction=_to_decimal(request.ohio_medical_deduction),
            ohio_qualifying_retirement_income=_to_decimal(
                request.ohio_qualifying_retirement_income
            ),
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
        default_sweep_ceiling=float(
            get_default_sweep_ceiling(result.filing_status, result.tax_year)
        ),
        default_sweep_ceiling_rate=float(get_default_sweep_ceiling_bracket_rate()),
        planning_signals=_compute_planning_signals(result, income, variable_ordinary),
    )
