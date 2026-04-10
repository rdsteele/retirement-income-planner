"""Total cost route — thin wrapper around calculate_total_cost service."""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from api.models.total_cost import (
    BracketBoundary,
    TotalCostComponents,
    TotalCostPlanningSignals,
    TotalCostPoints,
    TotalCostRequest,
    TotalCostResponse,
)
from services.emr import SweepMode
from services.emr import compute_planning_signals as _compute_service_signals
from services.total_cost import TotalCostResult, calculate_total_cost

logger = logging.getLogger(__name__)

router = APIRouter()

_D = Decimal
_ZERO = 0.0


def _to_decimal(value: float) -> Decimal:
    return _D(str(value))


def _to_decimal_or_none(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return _D(str(value))


def _build_points(result: TotalCostResult) -> TotalCostPoints:
    pts = result.points
    return TotalCostPoints(
        income=[float(p.income) for p in pts],
        total_tax=[float(p.total_tax) for p in pts],
        emr=[round(float(p.emr), 4) for p in pts],
        components=TotalCostComponents(
            ordinary=[round(float(p.emr_ordinary), 4) for p in pts],
            ss_torpedo=[round(float(p.emr_ss_torpedo), 4) for p in pts],
            pref_stacking=[round(float(p.emr_pref_stacking), 4) for p in pts],
            niit=[round(float(p.emr_niit), 4) for p in pts],
            ohio=[round(float(p.emr_ohio), 4) for p in pts],
            aca=[round(float(p.emr_aca), 4) for p in pts],
        ),
        ss_taxable=[float(p.ss_taxable) for p in pts],
        ss_inclusion_rate=[round(float(p.ss_inclusion_rate), 4) for p in pts],
        taxable_ordinary=[float(p.taxable_ordinary) for p in pts],
        ohio_tax=[float(p.ohio_tax) for p in pts],
        aca_magi=[float(p.aca_magi) for p in pts],
        aptc_annual=[float(p.aptc_annual) for p in pts],
        aca_subsidy_loss=[float(p.aca_subsidy_loss) for p in pts],
        emr_aca=[round(float(p.emr_aca), 4) for p in pts],
        total_cost_emr=[round(float(p.total_cost_emr), 4) for p in pts],
    )


def _to_float_or_none(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _compute_zero_rate_threshold(result: TotalCostResult) -> float | None:
    for p in result.points:
        if float(p.emr_ordinary) > _ZERO:
            return float(p.income)
    return None


def _compute_bracket_boundaries(result: TotalCostResult) -> list[BracketBoundary]:
    boundaries: list[BracketBoundary] = []
    prev_rate: float | None = None
    for p in result.points:
        rate = round(float(p.emr_ordinary), 4)
        if rate != prev_rate:
            pct = int(round(rate * 100))
            boundaries.append(
                BracketBoundary(
                    sweep_value=float(p.income),
                    rate=rate,
                    notes=f"{pct}% bracket",
                )
            )
            prev_rate = rate
    return boundaries


def _compute_planning_signals(
    result: TotalCostResult,
    request: TotalCostRequest,
    mode: SweepMode,
) -> TotalCostPlanningSignals:
    from typing import cast

    from services.emr import EMRPoint, EMRResult

    emr_result = EMRResult(
        sweep_mode=mode,
        points=cast(list[EMRPoint], result.points),
        irmaa_thresholds=result.irmaa_thresholds,
        tax_year=result.tax_year,
        filing_status=result.filing_status,
    )
    shared = _compute_service_signals(
        emr_result,
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

    zero_rate_threshold = _compute_zero_rate_threshold(result)
    bracket_boundaries = _compute_bracket_boundaries(result)

    aca_cliff_sweep_value: float | None = None
    if request.include_aca:
        aca_cliff_sweep_value = float(result.cliff_sweep_value)

    return TotalCostPlanningSignals(
        zero_ordinary_space=_to_float_or_none(shared.zero_ordinary_space),
        zero_rate_threshold=zero_rate_threshold,
        aca_cliff_sweep_value=aca_cliff_sweep_value,
        bracket_boundaries=bracket_boundaries,
        ltcg_0pct_remaining=_to_float_or_none(shared.ltcg_0pct_remaining),
        ltcg_0pct_ordinary_runway=_to_float_or_none(shared.ltcg_0pct_ordinary_runway),
        torpedo_active=shared.torpedo_active,
        ss_fully_taxable=shared.ss_fully_taxable,
        distance_to_22pct=_to_float_or_none(shared.distance_to_22pct),
        distance_to_24pct=_to_float_or_none(shared.distance_to_24pct),
    )


@router.post("/total-cost", response_model=TotalCostResponse)
def post_total_cost(request: TotalCostRequest):
    try:
        mode = SweepMode(request.sweep_mode)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sweep_mode: {request.sweep_mode!r}. "
            f"Must be 'ordinary' or 'preferential'.",
        )

    try:
        result = calculate_total_cost(
            pension=_to_decimal(request.pension),
            interest=_to_decimal(request.interest),
            ordinary_dividends=_to_decimal(request.ordinary_dividends),
            ira_distributions=_to_decimal(request.ira_distributions),
            ss_benefit=_to_decimal(request.ss_benefit),
            qualified_dividends=_to_decimal(request.qualified_dividends),
            fixed_ltcg=_to_decimal(request.fixed_ltcg),
            tax_exempt_interest=_to_decimal(request.tax_exempt_interest),
            above_the_line_adjustments=_to_decimal(request.above_the_line_adjustments),
            additional_deductions=_to_decimal(request.additional_deductions),
            sweep_mode=mode,
            variable_ordinary=_to_decimal(request.variable_ordinary),
            filing_status=request.filing_status,
            tax_year=request.tax_year,
            sweep_floor=_to_decimal(request.sweep_floor),
            sweep_ceiling=_to_decimal_or_none(request.sweep_ceiling),
            sweep_step=_to_decimal(request.sweep_step),
            include_ohio=request.include_ohio,
            ohio_medical_deduction=_to_decimal(request.ohio_medical_deduction),
            ohio_qualifying_retirement_income=_to_decimal(
                request.ohio_qualifying_retirement_income
            ),
            include_aca=request.include_aca,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error in total cost calculation")
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
        aca_cliff_magi=float(result.aca_cliff_magi),
        aptc_annual_max=float(result.aptc_annual_max),
        cliff_sweep_value=float(result.cliff_sweep_value),
        planning_signals=_compute_planning_signals(result, request, mode),
    )
