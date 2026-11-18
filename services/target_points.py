"""Target income points: where income should stop before the next costly stretch.

Given the running cost of an income sweep and a maximum acceptable effective marginal rate
(EMR), find the last income before each stretch whose EMR is above the maximum, and the
average EMR of each leg between those targets. Only legs whose average is within the
maximum are returned. Pure Python on a list of cost points, with no knowledge of the API
layer or of where the costs come from.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from services.common import round_rate

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
