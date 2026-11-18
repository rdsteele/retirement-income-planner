"""Target income points: where income should stop before the next costly stretch.

Given the running cost of an income sweep and a maximum acceptable effective marginal rate
(EMR), find the last income before each stretch whose EMR is above the maximum, and the
average EMR of each leg between those targets. Only legs whose average is within the
maximum are returned. Pure Python on a list of cost points, with no knowledge of the API
layer or of where the costs come from. ``calculate_target_points`` composes the total cost
sweep with that search.
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal

from services.common import round_rate
from services.emr import SweepMode
from services.income_inputs import IncomeInputs
from services.total_cost import TotalCostPoint, calculate_total_cost

_ZERO = Decimal("0")


@dataclass(frozen=True)
class CostPoint:
    """Cumulative annual cost at an income, and what drives the cost just above it."""

    income: Decimal
    cost: Decimal
    causes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TargetLeg:
    """The span between two consecutive targets, including any costly stretch inside it."""

    from_income: Decimal
    to_income: Decimal
    average_emr: Decimal
    cost: Decimal
    causes: tuple[str, ...]


@dataclass(frozen=True)
class TargetPointsResult:
    max_rate: Decimal
    targets: list[Decimal] = field(default_factory=list)
    legs: list[TargetLeg] = field(default_factory=list)
    # IRMAA thresholds the costs were computed with (empty when IRMAA is left out), so a
    # chart can draw its threshold lines where the targets were placed.
    irmaa_thresholds: list[Decimal] = field(default_factory=list)


def _require_valid_input(points: list[CostPoint], max_rate: Decimal) -> None:
    if max_rate < _ZERO:
        raise ValueError("max_rate must not be negative")
    if any(nxt.income <= cur.income for cur, nxt in zip(points, points[1:])):
        raise ValueError("points must be in increasing income order")


def _average_rate(start: CostPoint, end: CostPoint) -> Decimal:
    """Cost added per dollar of income between two points."""
    return (end.cost - start.cost) / (end.income - start.income)


def _hot_segments(points: list[CostPoint], max_rate: Decimal) -> list[bool]:
    """For each segment between adjacent points, whether its rate is above the maximum."""
    return [_average_rate(cur, nxt) > max_rate for cur, nxt in zip(points, points[1:])]


def _zone_starts(hot: list[bool]) -> list[int]:
    """Index of the point that opens each run of costly segments."""
    return [i for i, is_hot in enumerate(hot) if is_hot and (i == 0 or not hot[i - 1])]


def _target_indexes(hot: list[bool], last: int) -> list[int]:
    """Where targets sit: the sweep's start, each costly stretch's start, and its end."""
    return sorted({0, *_zone_starts(hot), last})


def _leg_causes(points: list[CostPoint], hot: list[bool], first: int, last: int) -> tuple[str, ...]:
    """What drives the costly segments inside the leg, in order of first appearance."""
    causes: dict[str, None] = {}
    for i in range(first, last):
        if hot[i]:
            causes.update(dict.fromkeys(points[i].causes))
    return tuple(causes)


def _build_leg(points: list[CostPoint], hot: list[bool], first: int, last: int) -> TargetLeg:
    start, end = points[first], points[last]
    return TargetLeg(
        from_income=start.income,
        to_income=end.income,
        average_emr=round_rate(_average_rate(start, end)),
        cost=end.cost - start.cost,
        causes=_leg_causes(points, hot, first, last),
    )


def _within_max(leg_points: tuple[CostPoint, CostPoint], max_rate: Decimal) -> bool:
    """Compare the unrounded average, so a rate just over the maximum is never let through."""
    return _average_rate(*leg_points) <= max_rate


def find_target_points(points: list[CostPoint], max_rate: Decimal) -> TargetPointsResult:
    """Find the targets and the desirable legs between them.

    ``points`` are in increasing income order with cumulative cost. A segment is costly when
    its cost per dollar is above ``max_rate``; consecutive costly segments form a stretch.
    Targets are the first income, the start of every costly stretch, and the last income.
    A leg is desirable when its average cost per dollar, with its costly stretch included,
    is at or below ``max_rate``.
    """
    _require_valid_input(points, max_rate)
    if len(points) < 2:
        return TargetPointsResult(max_rate=max_rate, targets=[p.income for p in points])

    hot = _hot_segments(points, max_rate)
    indexes = _target_indexes(hot, len(points) - 1)
    legs = [
        _build_leg(points, hot, first, last)
        for first, last in zip(indexes, indexes[1:])
        if _within_max((points[first], points[last]), max_rate)
    ]
    return TargetPointsResult(
        max_rate=max_rate, targets=[points[i].income for i in indexes], legs=legs
    )


# ---------------------------------------------------------------------------
# From a total cost sweep
# ---------------------------------------------------------------------------

CAUSE_BRACKET = "bracket"
CAUSE_SS_TORPEDO = "ss_torpedo"
CAUSE_PREF_STACKING = "pref_stacking"
CAUSE_NIIT = "niit"
CAUSE_ACA = "aca"
CAUSE_IRMAA = "irmaa"


def _total_cost_of(point: TotalCostPoint) -> Decimal:
    """Annual dollars the household has paid by this income: tax, lost subsidy, surcharge."""
    return point.total_tax + point.aca_subsidy_loss + point.irmaa_surcharge


def _causes_of(point: TotalCostPoint, max_rate: Decimal) -> tuple[str, ...]:
    """What is pushing the rate just above this income, from the EMR components."""
    candidates = [
        (point.emr_ordinary > max_rate, CAUSE_BRACKET),
        (point.emr_ss_torpedo > _ZERO, CAUSE_SS_TORPEDO),
        (point.emr_pref_stacking > _ZERO, CAUSE_PREF_STACKING),
        (point.emr_niit > _ZERO, CAUSE_NIIT),
        (point.emr_aca > _ZERO, CAUSE_ACA),
        (point.emr_irmaa > _ZERO, CAUSE_IRMAA),
    ]
    return tuple(name for active, name in candidates if active)


def to_cost_points(points: list[TotalCostPoint], max_rate: Decimal) -> list[CostPoint]:
    return [CostPoint(p.income, _total_cost_of(p), _causes_of(p, max_rate)) for p in points]


def calculate_target_points(
    *,
    income: IncomeInputs,
    filing_status: str,
    tax_year: int,
    max_rate: Decimal,
    sweep_mode: SweepMode = SweepMode.ORDINARY,
    variable_ordinary: Decimal = _ZERO,
    sweep_floor: Decimal = _ZERO,
    sweep_ceiling: Decimal | None = None,
    sweep_step: Decimal | None = None,
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
    ohio_qualifying_retirement_income: Decimal = _ZERO,
    include_aca: bool = False,
    include_irmaa: bool = True,
    irmaa_enrollees: int | None = None,
    irmaa_inflation_rate: Decimal | None = None,
) -> TargetPointsResult:
    """Run the total cost sweep and find the target points and desirable legs in it."""
    sweep = calculate_total_cost(
        income=income,
        filing_status=filing_status,
        tax_year=tax_year,
        sweep_mode=sweep_mode,
        variable_ordinary=variable_ordinary,
        sweep_floor=sweep_floor,
        sweep_ceiling=sweep_ceiling,
        sweep_step=sweep_step,
        include_ohio=include_ohio,
        ohio_medical_deduction=ohio_medical_deduction,
        ohio_qualifying_retirement_income=ohio_qualifying_retirement_income,
        include_aca=include_aca,
        include_irmaa=include_irmaa,
        irmaa_enrollees=irmaa_enrollees,
        irmaa_inflation_rate=irmaa_inflation_rate,
    )
    found = find_target_points(to_cost_points(sweep.points, max_rate), max_rate)
    return replace(found, irmaa_thresholds=sweep.irmaa_projected_thresholds)
