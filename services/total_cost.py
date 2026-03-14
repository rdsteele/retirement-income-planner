"""Total cost EMR service.

Combines federal tax, Ohio tax, and ACA subsidy loss into a single total cost
EMR curve. Thin orchestration layer over calculate_emr() and calculate_aca_subsidy().
"""

from dataclasses import dataclass
from decimal import Decimal

from services.aca import calculate_aca_subsidy
from services.emr import EMRPoint, EMRResult, SweepMode, calculate_emr

_ZERO = Decimal("0")
_EMR_COMPUTE_STEP = Decimal("1000")


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
    sweep_mode: SweepMode,
    sweep_value: Decimal,
    fixed_ordinary: Decimal,
    ss_taxable: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    above_the_line_adjustments: Decimal,
    tax_exempt_interest: Decimal,
) -> Decimal:
    if sweep_mode == SweepMode.ORDINARY:
        return (
            fixed_ordinary
            + sweep_value
            + ss_taxable
            - above_the_line_adjustments
            + tax_exempt_interest
        )
    else:  # PREFERENTIAL
        return (
            fixed_ordinary
            + qualified_dividends
            + fixed_ltcg
            + sweep_value
            + ss_taxable
            - above_the_line_adjustments
            + tax_exempt_interest
        )


def _compute_cliff_sweep_value(
    sweep_mode: SweepMode,
    cliff_magi: Decimal,
    fixed_ordinary: Decimal,
    ss_taxable_at_floor: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    above_the_line_adjustments: Decimal,
    tax_exempt_interest: Decimal,
) -> Decimal:
    base = (
        cliff_magi
        - fixed_ordinary
        - ss_taxable_at_floor
        + above_the_line_adjustments
        - tax_exempt_interest
    )
    if sweep_mode == SweepMode.PREFERENTIAL:
        base = base - fixed_ltcg - qualified_dividends
    return base


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
        aca_magi=_ZERO,
        aptc_annual=_ZERO,
        aca_subsidy_loss=_ZERO,
        emr_aca=_ZERO,
        total_cost_emr=emr_point.emr,
    )


def calculate_total_cost(
    *,
    pension: Decimal = _ZERO,
    interest: Decimal = _ZERO,
    ordinary_dividends: Decimal = _ZERO,
    ira_distributions: Decimal = _ZERO,
    ss_benefit: Decimal = _ZERO,
    qualified_dividends: Decimal = _ZERO,
    fixed_ltcg: Decimal = _ZERO,
    tax_exempt_interest: Decimal = _ZERO,
    above_the_line_adjustments: Decimal = _ZERO,
    additional_deductions: Decimal = _ZERO,
    sweep_mode: SweepMode = SweepMode.ORDINARY,
    variable_ordinary: Decimal = _ZERO,
    filing_status: str = "single",
    tax_year: int = 2026,
    sweep_floor: Decimal = _ZERO,
    sweep_ceiling: Decimal | None = None,
    sweep_step: Decimal = Decimal("100"),
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
    ohio_qualifying_retirement_income: Decimal = _ZERO,
    aptc_monthly: Decimal = _ZERO,
    include_aca: bool = False,
) -> TotalCostResult:
    fixed_ordinary = pension + interest + ordinary_dividends + ira_distributions
    if sweep_mode == SweepMode.PREFERENTIAL:
        fixed_ordinary = fixed_ordinary + variable_ordinary
    aptc_annual_known = aptc_monthly * 12

    extra_boundary_points: list[Decimal] | None = None
    cliff_sweep_value = _ZERO
    cliff_magi = _ZERO
    aptc_annual_max = _ZERO

    if include_aca:
        # Approximate ss_taxable at floor using a quick single-point EMR call.
        # We need it to compute cliff_sweep_value before the full sweep.
        floor_result = calculate_emr(
            pension=pension,
            interest=interest,
            ordinary_dividends=ordinary_dividends,
            ira_distributions=ira_distributions,
            ss_benefit=ss_benefit,
            qualified_dividends=qualified_dividends,
            fixed_ltcg=fixed_ltcg,
            tax_exempt_interest=tax_exempt_interest,
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
            above_the_line_adjustments=above_the_line_adjustments,
            additional_deductions=additional_deductions,
        )
        ss_taxable_at_floor = floor_result.points[0].ss_taxable if floor_result.points else _ZERO

        # ACA cliff MAGI from the floor-point ACA call
        aca_floor = calculate_aca_subsidy(
            magi=_compute_aca_magi(
                sweep_mode=sweep_mode,
                sweep_value=sweep_floor,
                fixed_ordinary=fixed_ordinary,
                ss_taxable=ss_taxable_at_floor,
                qualified_dividends=qualified_dividends,
                fixed_ltcg=fixed_ltcg,
                above_the_line_adjustments=above_the_line_adjustments,
                tax_exempt_interest=tax_exempt_interest,
            ),
            slcsp_annual_premium=_ZERO,
            filing_status=filing_status,
            tax_year=tax_year,
            known_aptc_annual=aptc_annual_known,
        )
        cliff_magi = aca_floor.cliff_magi
        aptc_annual_max = aca_floor.aptc_annual

        cliff_sweep_value = _compute_cliff_sweep_value(
            sweep_mode=sweep_mode,
            cliff_magi=cliff_magi,
            fixed_ordinary=fixed_ordinary,
            ss_taxable_at_floor=ss_taxable_at_floor,
            qualified_dividends=qualified_dividends,
            fixed_ltcg=fixed_ltcg,
            above_the_line_adjustments=above_the_line_adjustments,
            tax_exempt_interest=tax_exempt_interest,
        )
        extra_boundary_points = [cliff_sweep_value]

    emr_result: EMRResult = calculate_emr(
        pension=pension,
        interest=interest,
        ordinary_dividends=ordinary_dividends,
        ira_distributions=ira_distributions,
        ss_benefit=ss_benefit,
        qualified_dividends=qualified_dividends,
        fixed_ltcg=fixed_ltcg,
        tax_exempt_interest=tax_exempt_interest,
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
        above_the_line_adjustments=above_the_line_adjustments,
        additional_deductions=additional_deductions,
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
            sweep_mode=sweep_mode,
            sweep_value=p.income,
            fixed_ordinary=fixed_ordinary,
            ss_taxable=p.ss_taxable,
            qualified_dividends=qualified_dividends,
            fixed_ltcg=fixed_ltcg,
            above_the_line_adjustments=above_the_line_adjustments,
            tax_exempt_interest=tax_exempt_interest,
        )
        aca_result = calculate_aca_subsidy(
            magi=aca_magi,
            slcsp_annual_premium=_ZERO,
            filing_status=filing_status,
            tax_year=tax_year,
            known_aptc_annual=aptc_annual_known,
        )
        emr_aca = aca_result.marginal_subsidy_loss / _EMR_COMPUTE_STEP
        tc_points.append(TotalCostPoint(
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
            aca_magi=aca_magi,
            aptc_annual=aca_result.aptc_annual,
            aca_subsidy_loss=aca_result.subsidy_loss,
            emr_aca=emr_aca,
            total_cost_emr=p.emr + emr_aca,
        ))

    return TotalCostResult(
        points=tc_points,
        irmaa_thresholds=emr_result.irmaa_thresholds,
        tax_year=emr_result.tax_year,
        filing_status=emr_result.filing_status,
        aca_cliff_magi=cliff_magi,
        aptc_annual_max=aptc_annual_max,
        cliff_sweep_value=cliff_sweep_value,
    )
