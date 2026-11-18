"""Total cost EMR service.

Combines federal tax, Ohio tax, ACA subsidy loss, and the IRMAA surcharge into a single
total cost EMR curve. Thin orchestration layer over calculate_emr(),
calculate_aca_subsidy(), and the irmaa service.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from services.aca import calculate_aca_subsidy, get_aptc_schedule_magis
from services.data_loader import get_irmaa_inflation_default
from services.emr import (
    EMRPoint,
    EMRResult,
    SweepMode,
    calculate_emr,
    get_default_sweep_ceiling,
    magi_at_sweep_value,
)
from services.income_inputs import IncomeInputs
from services.irmaa import (
    annual_surcharge_at_tier,
    default_enrollees,
    irmaa_tier,
    projected_thresholds,
    require_valid_enrollees,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_TWO = Decimal("2")
_EMR_COMPUTE_STEP = Decimal("500")
_ACA_LOSS_UNIT = Decimal("1000")  # ACA service reports loss per $1,000 of MAGI
_IRMAA_LOSS_UNIT = Decimal("1000")  # IRMAA spikes are reported the same way


@dataclass
class TotalCostPoint(EMRPoint):
    # ACA additions
    aca_magi: Decimal
    aptc_annual: Decimal
    aca_subsidy_loss: Decimal
    emr_aca: Decimal
    # IRMAA additions
    irmaa_surcharge: Decimal
    emr_irmaa: Decimal
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
    irmaa_projected_thresholds: list[Decimal] = field(default_factory=list)


def _compute_aca_magi(
    sweep_value: Decimal,
    fixed_ordinary: Decimal,
    income: IncomeInputs,
) -> Decimal:
    """ACA modified AGI at a sweep point (IRS Pub. 974).

    AGI + tax-exempt interest + nontaxable Social Security. AGI holds the taxable part
    of SS, so the whole benefit is counted and the taxable portion drops out: this is
    linear in the sweep (no torpedo effect) and needs no EMR result.
    """
    return (
        fixed_ordinary
        + income.fixed_preferential
        + sweep_value
        + income.ss_benefit
        - income.above_the_line_adjustments
        + income.tax_exempt_interest
    )


def _compute_cliff_sweep_value(
    cliff_magi: Decimal,
    fixed_ordinary: Decimal,
    income: IncomeInputs,
) -> Decimal:
    """The sweep value at which ACA MAGI reaches ``cliff_magi`` (inverse of the above)."""
    return (
        cliff_magi
        - fixed_ordinary
        - income.fixed_preferential
        - income.ss_benefit
        + income.above_the_line_adjustments
        - income.tax_exempt_interest
    )


@dataclass(frozen=True)
class _AcaSetup:
    """ACA facts fixed by the floor of the sweep, plus the sweep points the ACA adds."""

    cliff_sweep_value: Decimal = _ZERO
    cliff_magi: Decimal = _ZERO
    aptc_annual_max: Decimal = _ZERO
    floor_aca_magi: Decimal = _ZERO
    boundary_points: list[Decimal] = field(default_factory=list)


@dataclass(frozen=True)
class _AcaAtPoint:
    aca_magi: Decimal = _ZERO
    aptc_annual: Decimal = _ZERO
    subsidy_loss: Decimal = _ZERO
    emr_aca: Decimal = _ZERO


@dataclass(frozen=True)
class _IrmaaSetup:
    """The projected thresholds, who pays, and the sweep points IRMAA adds."""

    thresholds: list[Decimal] = field(default_factory=list)
    enrollees: int = 0
    boundary_points: list[Decimal] = field(default_factory=list)


def _setup_aca(
    *,
    income: IncomeInputs,
    fixed_ordinary: Decimal,
    filing_status: str,
    tax_year: int,
    sweep_floor: Decimal,
    sweep_ceiling: Decimal | None,
) -> _AcaSetup:
    floor_aca_magi = _compute_aca_magi(
        sweep_value=sweep_floor, fixed_ordinary=fixed_ordinary, income=income
    )
    aca_floor = calculate_aca_subsidy(
        magi=floor_aca_magi,
        filing_status=filing_status,
        tax_year=tax_year,
        baseline_magi=floor_aca_magi,
    )
    cliff_magi = aca_floor.cliff_magi
    cliff_sweep_value = _compute_cliff_sweep_value(
        cliff_magi=cliff_magi, fixed_ordinary=fixed_ordinary, income=income
    )

    # Boundary points: cliff + all schedule MAGI points within sweep range
    effective_ceiling = sweep_ceiling if sweep_ceiling is not None else cliff_magi * 2
    boundary_points = [cliff_sweep_value]
    for sched_magi in get_aptc_schedule_magis(filing_status, tax_year):
        sched_sweep = _compute_cliff_sweep_value(
            cliff_magi=sched_magi, fixed_ordinary=fixed_ordinary, income=income
        )
        if sweep_floor <= sched_sweep <= effective_ceiling:
            boundary_points.append(sched_sweep)

    return _AcaSetup(
        cliff_sweep_value=cliff_sweep_value,
        cliff_magi=cliff_magi,
        aptc_annual_max=aca_floor.aptc_annual,
        floor_aca_magi=floor_aca_magi,
        boundary_points=boundary_points,
    )


def _round_to_dollar(value: Decimal) -> Decimal:
    return value.quantize(_ONE, rounding=ROUND_HALF_UP)


def _crossing_points(
    tier_at: Callable[[Decimal], int], tier: int, floor: Decimal, ceiling: Decimal
) -> list[Decimal]:
    """The last sweep value below ``tier`` and the first one in it, if the sweep crosses.

    Bisects on dollars: the tier never falls as the sweep rises, so the answer is the
    dollar where it changes. Returns nothing when the sweep starts in the tier or never
    reaches it.
    """
    if tier_at(floor) >= tier or tier_at(ceiling) < tier:
        return []
    below, reached = floor, ceiling
    while reached - below > _ONE:
        middle = _round_to_dollar((below + reached) / _TWO)
        if tier_at(middle) < tier:
            below = middle
        else:
            reached = middle
    return [below, reached]


def _irmaa_boundary_points(
    tier_at: Callable[[Decimal], int], tier_count: int, floor: Decimal, ceiling: Decimal
) -> list[Decimal]:
    """Sweep points on both sides of every IRMAA cliff the sweep crosses."""
    points: list[Decimal] = []
    for tier in range(1, tier_count + 1):
        points.extend(_crossing_points(tier_at, tier, floor, ceiling))
    return points


def _setup_irmaa(
    *,
    income: IncomeInputs,
    sweep_mode: SweepMode,
    variable_ordinary: Decimal,
    filing_status: str,
    tax_year: int,
    sweep_floor: Decimal,
    sweep_ceiling: Decimal | None,
    enrollees: int | None,
    inflation_rate: Decimal | None,
) -> _IrmaaSetup:
    paying = default_enrollees(filing_status) if enrollees is None else enrollees
    require_valid_enrollees(paying, filing_status)
    rate = get_irmaa_inflation_default() if inflation_rate is None else inflation_rate
    thresholds = projected_thresholds(filing_status, tax_year, rate)
    ceiling = (
        sweep_ceiling
        if sweep_ceiling is not None
        else get_default_sweep_ceiling(filing_status, tax_year)
    )

    def tier_at(sweep_value: Decimal) -> int:
        magi = magi_at_sweep_value(
            sweep_value, sweep_mode, income, variable_ordinary, filing_status
        )
        return irmaa_tier(magi, thresholds)

    boundary_points = _irmaa_boundary_points(tier_at, len(thresholds), sweep_floor, ceiling)
    return _IrmaaSetup(thresholds=thresholds, enrollees=paying, boundary_points=boundary_points)


def _aca_at_point(
    sweep_value: Decimal,
    setup: _AcaSetup,
    *,
    income: IncomeInputs,
    fixed_ordinary: Decimal,
    filing_status: str,
    tax_year: int,
) -> _AcaAtPoint:
    aca_magi = _compute_aca_magi(
        sweep_value=sweep_value, fixed_ordinary=fixed_ordinary, income=income
    )
    result = calculate_aca_subsidy(
        magi=aca_magi,
        filing_status=filing_status,
        tax_year=tax_year,
        baseline_magi=setup.floor_aca_magi,
    )
    return _AcaAtPoint(
        aca_magi=aca_magi,
        aptc_annual=result.aptc_annual,
        subsidy_loss=result.subsidy_loss,
        emr_aca=result.marginal_subsidy_loss / _ACA_LOSS_UNIT,
    )


def _irmaa_surcharges(points: list[EMRPoint], setup: _IrmaaSetup, tax_year: int) -> list[Decimal]:
    """The annual surcharge at each point, from its IRMAA MAGI."""
    return [
        annual_surcharge_at_tier(
            irmaa_tier(p.irmaa_magi, setup.thresholds), tax_year, setup.enrollees
        )
        for p in points
    ]


def _irmaa_spikes(surcharges: list[Decimal]) -> list[Decimal]:
    """Surcharge added by the next segment per $1,000, so a cliff shows as a spike."""
    increases = [nxt - cur for cur, nxt in zip(surcharges, surcharges[1:])]
    return [increase / _IRMAA_LOSS_UNIT for increase in [*increases, _ZERO]]


def _build_point(
    p: EMRPoint, aca: _AcaAtPoint, irmaa_surcharge: Decimal, emr_irmaa: Decimal
) -> TotalCostPoint:
    return TotalCostPoint(
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
        irmaa_magi=p.irmaa_magi,
        aca_magi=aca.aca_magi,
        aptc_annual=aca.aptc_annual,
        aca_subsidy_loss=aca.subsidy_loss,
        emr_aca=aca.emr_aca,
        irmaa_surcharge=irmaa_surcharge,
        emr_irmaa=emr_irmaa,
        total_cost_emr=p.emr + aca.emr_aca + emr_irmaa,
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
    include_irmaa: bool = False,
    irmaa_enrollees: int | None = None,
    irmaa_inflation_rate: Decimal | None = None,
) -> TotalCostResult:
    """Sweep the total cost EMR: tax, plus ACA subsidy loss and IRMAA when asked for.

    ``irmaa_enrollees`` is how many people pay the surcharge (default: everyone on the
    return). ``irmaa_inflation_rate`` grows the thresholds over the lookback to the premium
    year (default: the configured rate).
    """
    fixed_ordinary = income.fixed_ordinary
    if sweep_mode == SweepMode.PREFERENTIAL:
        fixed_ordinary = fixed_ordinary + variable_ordinary

    aca = _AcaSetup()
    if include_aca:
        aca = _setup_aca(
            income=income,
            fixed_ordinary=fixed_ordinary,
            filing_status=filing_status,
            tax_year=tax_year,
            sweep_floor=sweep_floor,
            sweep_ceiling=sweep_ceiling,
        )
    irmaa = _IrmaaSetup()
    if include_irmaa:
        irmaa = _setup_irmaa(
            income=income,
            sweep_mode=sweep_mode,
            variable_ordinary=variable_ordinary,
            filing_status=filing_status,
            tax_year=tax_year,
            sweep_floor=sweep_floor,
            sweep_ceiling=sweep_ceiling,
            enrollees=irmaa_enrollees,
            inflation_rate=irmaa_inflation_rate,
        )

    extra_boundary_points = [*aca.boundary_points, *irmaa.boundary_points] or None
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

    surcharges = _irmaa_surcharges(emr_result.points, irmaa, tax_year)
    spikes = _irmaa_spikes(surcharges)
    acas = [
        _aca_at_point(
            p.income,
            aca,
            income=income,
            fixed_ordinary=fixed_ordinary,
            filing_status=filing_status,
            tax_year=tax_year,
        )
        if include_aca
        else _AcaAtPoint()
        for p in emr_result.points
    ]
    points = [
        _build_point(p, a, surcharge, spike)
        for p, a, surcharge, spike in zip(emr_result.points, acas, surcharges, spikes)
    ]

    return TotalCostResult(
        points=points,
        irmaa_thresholds=emr_result.irmaa_thresholds,
        tax_year=emr_result.tax_year,
        filing_status=emr_result.filing_status,
        aca_cliff_magi=aca.cliff_magi,
        aptc_annual_max=aca.aptc_annual_max,
        cliff_sweep_value=aca.cliff_sweep_value,
        irmaa_projected_thresholds=irmaa.thresholds,
    )
