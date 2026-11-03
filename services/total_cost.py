"""Total cost EMR service.

Combines federal tax, Ohio tax, and ACA subsidy loss into a single total cost
EMR curve. Thin orchestration layer over calculate_emr() and calculate_aca_subsidy().
"""

from dataclasses import dataclass
from decimal import Decimal

from services.aca import calculate_aca_subsidy, get_aptc_schedule_magis
from services.emr import EMRPoint, EMRResult, SweepMode, calculate_emr
from services.income_inputs import IncomeInputs

_ZERO = Decimal("0")
_EMR_COMPUTE_STEP = Decimal("500")
_ACA_LOSS_UNIT = Decimal("1000")  # ACA service reports loss per $1,000 of MAGI


@dataclass
class TotalCostPoint(EMRPoint):
    # ACA additions
    aca_magi: Decimal
    aptc_annual: Decimal
    aca_subsidy_loss: Decimal
    emr_aca: Decimal
    # Total
    total_cost_emr: Decimal


@dataclass
class TotalCostResult:
    points: list[TotalCostPoint]
    irmaa_thresholds: list
    tax_year: int
    filing_status: str
    aca_cliff_magi: Decimal
    aptc_annual_max: Decimal
    cliff_sweep_value: Decimal


def _compute_aca_magi(
    sweep_value: Decimal,
    fixed_ordinary: Decimal,
    ss_taxable: Decimal,
    income: IncomeInputs,
) -> Decimal:
    return (
        fixed_ordinary
        + income.fixed_preferential
        + sweep_value
        + ss_taxable
        - income.above_the_line_adjustments
        + income.tax_exempt_interest
    )


def _compute_cliff_sweep_value(
    cliff_magi: Decimal,
    fixed_ordinary: Decimal,
    ss_taxable_at_floor: Decimal,
    income: IncomeInputs,
) -> Decimal:
    return (
        cliff_magi
        - fixed_ordinary
        - income.fixed_preferential
        - ss_taxable_at_floor
        + income.above_the_line_adjustments
        - income.tax_exempt_interest
    )


def _make_zero_aca_point(emr_point: EMRPoint) -> TotalCostPoint:
    return TotalCostPoint(
        income=emr_point.income,
        total_tax=emr_point.total_tax,
        emr=emr_point.emr,
        emr_ordinary=emr_point.emr_ordinary,
        emr_ss_torpedo=emr_point.emr_ss_torpedo,
        emr_pref_stacking=emr_point.emr_pref_stacking,
        emr_niit=emr_point.emr_niit,
        emr_ohio=emr_point.emr_ohio,
        ohio_tax=emr_point.ohio_tax,
        ss_taxable=emr_point.ss_taxable,
        ss_inclusion_rate=emr_point.ss_inclusion_rate,
        taxable_ordinary=emr_point.taxable_ordinary,
        taxable_preferential=emr_point.taxable_preferential,
        aca_magi=_ZERO,
        aptc_annual=_ZERO,
        aca_subsidy_loss=_ZERO,
        emr_aca=_ZERO,
        total_cost_emr=emr_point.emr,
    )


def calculate_total_cost(
    *,
    income: IncomeInputs,
    filing_status: str,
    tax_year: int,
    sweep_mode: SweepMode = SweepMode.ORDINARY,
    variable_ordinary: Decimal = _ZERO,
    sweep_floor: Decimal = _ZERO,
    sweep_ceiling: Decimal | None = None,
    sweep_step: Decimal | None = None,
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
    ohio_qualifying_retirement_income: Decimal = _ZERO,
    include_aca: bool = False,
) -> TotalCostResult:
    fixed_ordinary = income.fixed_ordinary
    if sweep_mode == SweepMode.PREFERENTIAL:
        fixed_ordinary = fixed_ordinary + variable_ordinary

    extra_boundary_points: list[Decimal] | None = None
    cliff_sweep_value = _ZERO
    cliff_magi = _ZERO
    aptc_annual_max = _ZERO
    floor_aca_magi = _ZERO

    if include_aca:
        # Approximate ss_taxable at floor using a quick single-point EMR call.
        # We need it to compute cliff_sweep_value before the full sweep.
        floor_result = calculate_emr(
            income=income,
            sweep_mode=sweep_mode,
            variable_ordinary=variable_ordinary,
            filing_status=filing_status,
            tax_year=tax_year,
            sweep_floor=sweep_floor,
            sweep_ceiling=sweep_floor,  # single point
            sweep_step=sweep_step,
            include_ohio=include_ohio,
            ohio_medical_deduction=ohio_medical_deduction,
            ohio_qualifying_retirement_income=ohio_qualifying_retirement_income,
        )
        ss_taxable_at_floor = floor_result.points[0].ss_taxable if floor_result.points else _ZERO

        floor_aca_magi = _compute_aca_magi(
            sweep_value=sweep_floor,
            fixed_ordinary=fixed_ordinary,
            ss_taxable=ss_taxable_at_floor,
            income=income,
        )

        # ACA cliff and max APTC from floor-point call
        aca_floor = calculate_aca_subsidy(
            magi=floor_aca_magi,
            filing_status=filing_status,
            tax_year=tax_year,
            baseline_magi=floor_aca_magi,
        )
        cliff_magi = aca_floor.cliff_magi
        aptc_annual_max = aca_floor.aptc_annual

        cliff_sweep_value = _compute_cliff_sweep_value(
            cliff_magi=cliff_magi,
            fixed_ordinary=fixed_ordinary,
            ss_taxable_at_floor=ss_taxable_at_floor,
            income=income,
        )

        # Boundary points: cliff + all schedule MAGI points within sweep range
        effective_ceiling = sweep_ceiling if sweep_ceiling is not None else cliff_magi * 2
        extra_boundary_points = [cliff_sweep_value]
        for sched_magi in get_aptc_schedule_magis(filing_status, tax_year):
            sched_sweep = _compute_cliff_sweep_value(
                cliff_magi=sched_magi,
                fixed_ordinary=fixed_ordinary,
                ss_taxable_at_floor=ss_taxable_at_floor,
                income=income,
            )
            if sweep_floor <= sched_sweep <= effective_ceiling:
                extra_boundary_points.append(sched_sweep)

    emr_result: EMRResult = calculate_emr(
        income=income,
        sweep_mode=sweep_mode,
        variable_ordinary=variable_ordinary,
        filing_status=filing_status,
        tax_year=tax_year,
        sweep_floor=sweep_floor,
        sweep_ceiling=sweep_ceiling,
        sweep_step=sweep_step,
        include_ohio=include_ohio,
        ohio_medical_deduction=ohio_medical_deduction,
        ohio_qualifying_retirement_income=ohio_qualifying_retirement_income,
        extra_boundary_points=extra_boundary_points,
    )

    if not include_aca:
        points = [_make_zero_aca_point(p) for p in emr_result.points]
        return TotalCostResult(
            points=points,
            irmaa_thresholds=emr_result.irmaa_thresholds,
            tax_year=emr_result.tax_year,
            filing_status=emr_result.filing_status,
            aca_cliff_magi=_ZERO,
            aptc_annual_max=_ZERO,
            cliff_sweep_value=_ZERO,
        )

    # Build TotalCostPoints with ACA overlay
    tc_points: list[TotalCostPoint] = []
    for p in emr_result.points:
        aca_magi = _compute_aca_magi(
            sweep_value=p.income,
            fixed_ordinary=fixed_ordinary,
            ss_taxable=p.ss_taxable,
            income=income,
        )
        aca_result = calculate_aca_subsidy(
            magi=aca_magi,
            filing_status=filing_status,
            tax_year=tax_year,
            baseline_magi=floor_aca_magi,
        )
        emr_aca = aca_result.marginal_subsidy_loss / _ACA_LOSS_UNIT
        tc_points.append(
            TotalCostPoint(
                income=p.income,
                total_tax=p.total_tax,
                emr=p.emr,
                emr_ordinary=p.emr_ordinary,
                emr_ss_torpedo=p.emr_ss_torpedo,
                emr_pref_stacking=p.emr_pref_stacking,
                emr_niit=p.emr_niit,
                emr_ohio=p.emr_ohio,
                ohio_tax=p.ohio_tax,
                ss_taxable=p.ss_taxable,
                ss_inclusion_rate=p.ss_inclusion_rate,
                taxable_ordinary=p.taxable_ordinary,
                taxable_preferential=p.taxable_preferential,
                aca_magi=aca_magi,
                aptc_annual=aca_result.aptc_annual,
                aca_subsidy_loss=aca_result.subsidy_loss,
                emr_aca=emr_aca,
                total_cost_emr=p.emr + emr_aca,
            )
        )

    return TotalCostResult(
        points=tc_points,
        irmaa_thresholds=emr_result.irmaa_thresholds,
        tax_year=emr_result.tax_year,
        filing_status=emr_result.filing_status,
        aca_cliff_magi=cliff_magi,
        aptc_annual_max=aptc_annual_max,
        cliff_sweep_value=cliff_sweep_value,
    )
