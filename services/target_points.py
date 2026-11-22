"""Target income points: where income should stop before the next costly stretch.

Given the running cost of an income sweep and a maximum acceptable effective marginal rate
(EMR), find the last income before each stretch whose EMR is above the maximum, and the
average EMR of each leg between those targets. Only legs whose average is within the
maximum are returned. Costs are rounded to whole dollars, so the rate between two close
points is noisy; a point's own ``rate`` (measured over a wider window) says whether its
stretch is costly, and the cost between points only confirms where the stretch begins. Pure Python on a list of cost points, with no knowledge of the API
layer or of where the costs come from. ``calculate_target_points`` composes the total cost
sweep with that search.
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal

from services.common import round_rate
from services.data_loader import get_irmaa_inflation_default, get_target_min_excess_cost
from services.emr import SweepMode
from services.income_inputs import IncomeInputs
from services.irmaa import projected_thresholds
from services.total_cost import TotalCostPoint, TotalCostResult, calculate_total_cost

_ZERO = Decimal("0")


@dataclass(frozen=True)
class CostPoint:
    """Cumulative annual cost at an income, and the marginal rate just above it.

    ``rate`` is the cost of the next dollar measured over a window wide enough to be free
    of rounding noise (a cliff shows as a very large rate). ``causes`` say what drives it.
    """

    income: Decimal
    cost: Decimal
    rate: Decimal
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
    # IRMAA thresholds for the requested growth (the ones the costs used when IRMAA is
    # included), so a chart can draw its threshold lines where the targets were placed.
    irmaa_thresholds: list[Decimal] = field(default_factory=list)
    # The spans between neighbouring targets whose average is above the maximum: what it
    # would cost to push through to the next target.
    over_max_legs: list[TargetLeg] = field(default_factory=list)
    # Spans between neighbouring targets that are within the maximum but lie past a span
    # that no later target recovers, so they are only reached by paying that span.
    unreachable_legs: list[TargetLeg] = field(default_factory=list)


def _require_valid_input(points: list[CostPoint], max_rate: Decimal) -> None:
    if max_rate < _ZERO:
        raise ValueError("max_rate must not be negative")
    if any(nxt.income <= cur.income for cur, nxt in zip(points, points[1:])):
        raise ValueError("points must be in increasing income order")


def _average_rate(start: CostPoint, end: CostPoint) -> Decimal:
    """Cost added per dollar of income between two points."""
    return (end.cost - start.cost) / (end.income - start.income)


def _rate_runs(costly: list[bool]) -> list[tuple[int, int]]:
    """First and last index of each run of consecutive True values."""
    runs: list[tuple[int, int]] = []
    for i, is_costly in enumerate(costly):
        if not is_costly:
            continue
        if runs and runs[-1][1] == i - 1:
            runs[-1] = (runs[-1][0], i)
        else:
            runs.append((i, i))
    return runs


def _first_costly_segment(
    points: list[CostPoint], run: tuple[int, int], max_rate: Decimal
) -> int | None:
    """The first point in the run whose own segment costs more than the maximum, if any.

    A point's rate looks ahead, so the run can begin a little before the real stretch; the
    cost of the segment itself places the start exactly. A run with no such segment is
    rounding noise.
    """
    first, last = run
    return next(
        (i for i in range(first, last + 1) if _average_rate(points[i], points[i + 1]) > max_rate),
        None,
    )


def _excess_cost(points: list[CostPoint], first: int, last: int, max_rate: Decimal) -> Decimal:
    """Dollars paid over what the maximum rate would cost, over the segments costing more.

    Segments at or under the maximum are left out, so a long cheap stretch after the
    costly one cannot hide it.
    """
    segments = zip(points[first:last], points[first + 1 : last + 1])
    excesses = ((b.cost - a.cost) - max_rate * (b.income - a.income) for a, b in segments)
    return sum((e for e in excesses if e > _ZERO), _ZERO)


def _hot_segments(
    points: list[CostPoint], max_rate: Decimal, min_excess: Decimal = _ZERO
) -> list[bool]:
    """For each segment between adjacent points, whether it is inside a costly stretch.

    A stretch is a run of points whose rate is above the maximum, from the first segment
    that really costs more than the maximum to the end of the run. A stretch that costs
    less than ``min_excess`` dollars over the maximum is not worth a target.
    """
    costly = [point.rate > max_rate for point in points[:-1]]
    hot = [False] * len(costly)
    for run in _rate_runs(costly):
        start = _first_costly_segment(points, run, max_rate)
        if start is not None and _excess_cost(points, start, run[1] + 1, max_rate) >= min_excess:
            hot[start : run[1] + 1] = [True] * (run[1] + 1 - start)
    return hot


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


def _leg_end(
    points: list[CostPoint], indexes: list[int], pos: int, max_rate: Decimal
) -> int | None:
    """Position of the target where the desirable leg starting at ``pos`` ends, if there is one.

    The leg normally ends at the next target. When that span is too costly, a later target
    can still be reachable because the rate falls back under the maximum: the farthest one
    whose average from ``pos`` fits ends the leg, so an undesirable stretch is taken to
    reach the desirable income beyond it.
    """

    def fits(end: int) -> bool:
        return _within_max((points[indexes[pos]], points[indexes[end]]), max_rate)

    if fits(pos + 1):
        return pos + 1
    reachable = [end for end in range(pos + 2, len(indexes)) if fits(end)]
    return reachable[-1] if reachable else None


def _desirable_spans(
    points: list[CostPoint], indexes: list[int], max_rate: Decimal
) -> list[tuple[int, int]]:
    """First and last point index of each desirable leg, in order.

    The walk ends at the first span that no later target brings back under the maximum:
    income beyond it is only reached by paying that span, so it is not desirable.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(indexes) - 1:
        end = _leg_end(points, indexes, pos, max_rate)
        if end is None:
            break  # what lies beyond cannot be reached without paying an unrecovered stretch
        spans.append((indexes[pos], indexes[end]))
        pos = end
    return spans


def _over_max_spans(
    points: list[CostPoint], candidates: list[int], max_rate: Decimal
) -> list[tuple[int, int]]:
    """Each span between neighbouring targets that costs more than the maximum on average."""
    return [
        (first, last)
        for first, last in zip(candidates, candidates[1:])
        if not _within_max((points[first], points[last]), max_rate)
    ]


def _unreachable_spans(
    points: list[CostPoint],
    candidates: list[int],
    spans: list[tuple[int, int]],
    max_rate: Decimal,
) -> list[tuple[int, int]]:
    """Neighbouring-target spans within the maximum that lie beyond the last desirable leg."""
    reached = spans[-1][1] if spans else candidates[0]
    return [
        (first, last)
        for first, last in zip(candidates, candidates[1:])
        if first > reached and _within_max((points[first], points[last]), max_rate)
    ]


def find_target_points(
    points: list[CostPoint], max_rate: Decimal, min_excess: Decimal = _ZERO
) -> TargetPointsResult:
    """Find the targets and the desirable legs between them.

    ``points`` are in increasing income order with cumulative cost and the marginal rate
    above each. A point is costly when its rate is above ``max_rate``; consecutive costly
    points form a stretch, which begins at its first segment that really costs more than
    ``max_rate`` and costs at least ``min_excess`` dollars more than that rate would.
    Candidate targets are the first income, the start of every costly stretch, and the last
    income.
    A leg is desirable when its average cost per dollar, with any costly stretch inside it
    included, is at or below ``max_rate``. ``over_max_legs`` lists the neighbouring-target
    spans that are not, and ``unreachable_legs`` those that are but lie past one that
    cannot be recovered. When the span to the next target is not, a later
    target is used if the average to it fits.
    """
    _require_valid_input(points, max_rate)
    if len(points) < 2:
        return TargetPointsResult(max_rate=max_rate, targets=[p.income for p in points])

    hot = _hot_segments(points, max_rate, min_excess)
    candidates = _target_indexes(hot, len(points) - 1)
    spans = _desirable_spans(points, candidates, max_rate)
    legs = [_build_leg(points, hot, first, last) for first, last in spans]
    unreachable = [
        _build_leg(points, hot, first, last)
        for first, last in _unreachable_spans(points, candidates, spans, max_rate)
    ]
    over = [
        _build_leg(points, hot, first, last)
        for first, last in _over_max_spans(points, candidates, max_rate)
    ]
    return TargetPointsResult(
        max_rate=max_rate,
        targets=[points[i].income for i in candidates],
        legs=legs,
        over_max_legs=over,
        unreachable_legs=unreachable,
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
    return [
        CostPoint(p.income, _total_cost_of(p), p.total_cost_emr, _causes_of(p, max_rate))
        for p in points
    ]


def _thresholds_reported(
    sweep: TotalCostResult,
    filing_status: str,
    tax_year: int,
    inflation_rate: Decimal | None,
) -> list[Decimal]:
    """The thresholds the sweep used, or the ones for the same growth when IRMAA was left out."""
    if sweep.irmaa_projected_thresholds:
        return sweep.irmaa_projected_thresholds
    rate = get_irmaa_inflation_default() if inflation_rate is None else inflation_rate
    return projected_thresholds(filing_status, tax_year, rate)


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
    found = find_target_points(
        to_cost_points(sweep.points, max_rate), max_rate, get_target_min_excess_cost()
    )
    thresholds = _thresholds_reported(sweep, filing_status, tax_year, irmaa_inflation_rate)
    return replace(found, irmaa_thresholds=thresholds)
