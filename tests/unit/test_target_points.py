"""Unit tests for services.target_points: the pure search for targets and desirable legs."""

from decimal import Decimal

import pytest

from services.target_points import CostPoint, find_target_points

D = Decimal


def _curve(*stretches, causes=None):
    """Cost points from (width, rate) stretches, starting at income 0 with no cost.

    A stretch is sampled every 1,000 of income; a stretch of width 1 is a single step, so a
    ``rate`` above 1 models a cliff. ``causes`` maps a stretch's position to its cause.
    """
    causes = causes or {}
    points = [CostPoint(D("0"), D("0"))]
    for index, (width, rate) in enumerate(stretches):
        step = min(D(width), D("1000"))
        steps = int(D(width) / step)
        for _ in range(steps):
            last = points[-1]
            # the point whose segment this is carries the cause of the segment above it
            points[-1] = CostPoint(last.income, last.cost, causes.get(index, ()))
            points.append(CostPoint(last.income + step, last.cost + step * D(rate)))
    return points


class TestNoCostlyStretch:
    def test_one_leg_from_start_to_end(self):
        result = find_target_points(_curve((100000, "0.20")), D("0.25"))
        assert result.targets == [D("0"), D("100000")]
        assert len(result.legs) == 1
        leg = result.legs[0]
        assert (leg.from_income, leg.to_income) == (D("0"), D("100000"))
        assert leg.average_emr == D("0.2000")
        assert leg.cost == D("20000")

    def test_segment_exactly_at_the_maximum_is_not_costly(self):
        result = find_target_points(_curve((50000, "0.25")), D("0.25"))
        assert result.targets == [D("0"), D("50000")]
        assert len(result.legs) == 1


class TestOneCostlyStretch:
    # 10% to 50,000, then 40% for 10,000, then 15%
    points = _curve((50000, "0.10"), (10000, "0.40"), (140000, "0.15"))

    def test_target_is_the_last_income_before_the_stretch(self):
        result = find_target_points(self.points, D("0.25"))
        assert result.targets == [D("0"), D("50000"), D("200000")]

    def test_legs_average_the_whole_span_including_the_stretch(self):
        result = find_target_points(self.points, D("0.25"))
        first, second = result.legs
        assert (first.from_income, first.to_income, first.average_emr) == (
            D("0"),
            D("50000"),
            D("0.1000"),
        )
        # 4,000 for the stretch + 21,000 above it, over 150,000
        assert (second.from_income, second.to_income) == (D("50000"), D("200000"))
        assert second.cost == D("25000")
        assert second.average_emr == D("0.1667")

    def test_a_leg_above_the_maximum_is_dropped(self):
        result = find_target_points(self.points, D("0.12"))
        assert [(leg.from_income, leg.to_income) for leg in result.legs] == [(D("0"), D("50000"))]
        assert result.targets == [D("0"), D("50000"), D("200000")]

    def test_maximum_below_every_rate_leaves_no_legs(self):
        result = find_target_points(self.points, D("0.05"))
        assert result.legs == []


class TestCliff:
    # 20% to 100,000, then a one-dollar step costing 5,000, then 20% again
    points = [
        CostPoint(D("0"), D("0")),
        CostPoint(D("100000"), D("20000")),
        CostPoint(D("100001"), D("25000.20")),
        CostPoint(D("200000"), D("45000.00")),
    ]

    def test_target_sits_on_the_last_dollar_before_the_cliff(self):
        result = find_target_points(self.points, D("0.25"))
        assert result.targets == [D("0"), D("100000"), D("200000")]

    def test_the_cliff_is_counted_in_the_next_leg_average(self):
        result = find_target_points(self.points, D("0.25"))
        assert len(result.legs) == 2
        # 25,000 over 100,000
        assert result.legs[1].average_emr == D("0.2500")

    def test_a_leg_whose_cliff_pushes_it_over_the_maximum_is_dropped(self):
        result = find_target_points(self.points, D("0.24"))
        assert [(leg.from_income, leg.to_income) for leg in result.legs] == [(D("0"), D("100000"))]


class TestSeveralStretches:
    # 10% | 40% for 10,000 | 10% for 40,000 | cliff | 10% | 40% for 10,000 | 10%
    points = [
        *_curve((50000, "0.10"), (10000, "0.40"), (40000, "0.10")),
    ]
    points += [
        CostPoint(D("100001"), points[-1].cost + D("4000")),
        CostPoint(D("150000"), points[-1].cost + D("4000") + D("49999") * D("0.10")),
    ]

    def test_every_stretch_opens_a_target(self):
        result = find_target_points(self.points, D("0.25"))
        assert result.targets == [D("0"), D("50000"), D("100000"), D("150000")]

    def test_leg_averages(self):
        result = find_target_points(self.points, D("0.25"))
        assert [leg.average_emr for leg in result.legs] == [D("0.1000"), D("0.1600"), D("0.1800")]


class TestEdges:
    def test_sweep_that_starts_inside_a_costly_stretch(self):
        result = find_target_points(_curve((10000, "0.40"), (90000, "0.10")), D("0.25"))
        assert result.targets == [D("0"), D("100000")]
        # 4,000 + 9,000 over 100,000
        assert result.legs[0].average_emr == D("0.1300")

    def test_sweep_that_ends_inside_a_costly_stretch(self):
        result = find_target_points(_curve((90000, "0.10"), (10000, "0.40")), D("0.25"))
        assert result.targets == [D("0"), D("90000"), D("100000")]
        assert [(leg.from_income, leg.to_income) for leg in result.legs] == [(D("0"), D("90000"))]

    def test_one_point_has_a_target_and_no_legs(self):
        result = find_target_points([CostPoint(D("5"), D("1"))], D("0.25"))
        assert result.targets == [D("5")]
        assert result.legs == []

    def test_no_points_has_nothing(self):
        result = find_target_points([], D("0.25"))
        assert result.targets == [] and result.legs == []

    def test_result_remembers_the_maximum(self):
        assert find_target_points([], D("0.30")).max_rate == D("0.30")

    def test_unsorted_points_are_rejected(self):
        points = [CostPoint(D("10"), D("0")), CostPoint(D("5"), D("1"))]
        with pytest.raises(ValueError, match="increasing"):
            find_target_points(points, D("0.25"))

    def test_repeated_income_is_rejected(self):
        points = [CostPoint(D("5"), D("0")), CostPoint(D("5"), D("1"))]
        with pytest.raises(ValueError, match="increasing"):
            find_target_points(points, D("0.25"))

    def test_negative_maximum_is_rejected(self):
        with pytest.raises(ValueError, match="negative"):
            find_target_points([], D("-0.01"))

    def test_average_just_over_the_maximum_is_not_let_through_by_rounding(self):
        points = [CostPoint(D("0"), D("0")), CostPoint(D("1000000"), D("250001"))]
        assert find_target_points(points, D("0.25")).legs == []


class TestCauses:
    def test_leg_lists_what_drove_its_costly_stretch(self):
        points = _curve(
            (50000, "0.10"),
            (10000, "0.40"),
            (140000, "0.15"),
            causes={1: ("torpedo",)},
        )
        result = find_target_points(points, D("0.25"))
        assert result.legs[0].causes == ()
        assert result.legs[1].causes == ("torpedo",)

    def test_causes_are_listed_once_in_order(self):
        points = [
            CostPoint(D("0"), D("0"), ("irmaa",)),
            CostPoint(D("1"), D("5000"), ("aca", "irmaa")),
            CostPoint(D("2"), D("10000"), ()),
            CostPoint(D("1000000"), D("10000")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.legs[0].causes == ("irmaa", "aca")

    def test_costly_segments_only_contribute_their_causes(self):
        points = [
            CostPoint(D("0"), D("0"), ("cheap",)),
            CostPoint(D("1000"), D("100"), ("irmaa",)),
            CostPoint(D("1001"), D("5100"), ()),
            CostPoint(D("100000"), D("20000")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.legs[0].causes == ()
        assert result.legs[1].causes == ("irmaa",)
