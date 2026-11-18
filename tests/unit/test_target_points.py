"""Unit tests for services.target_points: the pure search for targets and desirable legs."""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from services.target_points import CostPoint, find_target_points

D = Decimal


def _curve(*stretches, causes=None):
    """Cost points from (width, rate) stretches, starting at income 0 with no cost.

    A stretch is sampled every 1,000 of income. Each point's rate is that of the stretch
    above it, as the sweep's own marginal rate would be. ``causes`` maps a stretch's
    position to its cause.
    """
    causes = causes or {}
    points = []
    income, cost = D("0"), D("0")
    for index, (width, rate) in enumerate(stretches):
        step = min(D(width), D("1000"))
        for _ in range(int(D(width) / step)):
            points.append(CostPoint(income, cost, D(rate), causes.get(index, ())))
            income += step
            cost += step * D(rate)
    last_rate = D(stretches[-1][1])
    return [*points, CostPoint(income, cost, last_rate)]


class TestNoCostlyStretch:
    def test_one_leg_from_start_to_end(self):
        result = find_target_points(_curve((100000, "0.20")), D("0.25"))
        assert result.targets == [D("0"), D("100000")]
        assert len(result.legs) == 1
        leg = result.legs[0]
        assert (leg.from_income, leg.to_income) == (D("0"), D("100000"))
        assert leg.average_emr == D("0.2000")
        assert leg.cost == D("20000")

    def test_rate_exactly_at_the_maximum_is_not_costly(self):
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
    # 20% to 100,000, then a one-dollar step costing 5,000, then 20% again. The point
    # before a cliff carries the cliff's spike as its rate.
    points = [
        CostPoint(D("0"), D("0"), D("0.20")),
        CostPoint(D("100000"), D("20000"), D("5000")),
        CostPoint(D("100001"), D("25000.20"), D("0.20")),
        CostPoint(D("200000"), D("45000.00"), D("0.20")),
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
        CostPoint(D("0"), D("0"), D("0.10")),
        CostPoint(D("50000"), D("5000"), D("0.40")),
        CostPoint(D("60000"), D("9000"), D("0.10")),
        CostPoint(D("100000"), D("13000"), D("4000")),
        CostPoint(D("100001"), D("17000"), D("0.10")),
        CostPoint(D("150000"), D("21999.9"), D("0.10")),
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
        result = find_target_points([CostPoint(D("5"), D("1"), D("0"))], D("0.25"))
        assert result.targets == [D("5")]
        assert result.legs == []

    def test_no_points_has_nothing(self):
        result = find_target_points([], D("0.25"))
        assert result.targets == [] and result.legs == []

    def test_result_remembers_the_maximum(self):
        assert find_target_points([], D("0.30")).max_rate == D("0.30")

    def test_unsorted_points_are_rejected(self):
        points = [CostPoint(D("10"), D("0"), D("0")), CostPoint(D("5"), D("1"), D("0"))]
        with pytest.raises(ValueError, match="increasing"):
            find_target_points(points, D("0.25"))

    def test_repeated_income_is_rejected(self):
        points = [CostPoint(D("5"), D("0"), D("0")), CostPoint(D("5"), D("1"), D("0"))]
        with pytest.raises(ValueError, match="increasing"):
            find_target_points(points, D("0.25"))

    def test_negative_maximum_is_rejected(self):
        with pytest.raises(ValueError, match="negative"):
            find_target_points([], D("-0.01"))

    def test_average_just_over_the_maximum_is_not_let_through_by_rounding(self):
        points = [
            CostPoint(D("0"), D("0"), D("0.10")),
            CostPoint(D("1000000"), D("250001"), D("0.10")),
        ]
        assert find_target_points(points, D("0.25")).legs == []


def _rounded(income, rate):
    """Cost at an income with the tax rounded to whole dollars, as the real sweep does."""
    return (income * D(rate)).quantize(D("1"), rounding=ROUND_HALF_UP)


class TestRoundingNoise:
    def test_a_rate_just_over_the_maximum_is_one_stretch_not_many(self):
        # 10% to 5,000, then a true rate of 24.75% sampled every 100 with whole-dollar costs:
        # segments alternate between 24 and 25 dollars, so some segments equal 24%.
        def cost_at(income):
            beyond = max(income - 5000, D("0"))
            return _rounded(min(income, D("5000")) * D("0.10") + beyond * D("0.2475"), "1")

        points = [
            CostPoint(D(i * 100), cost_at(D(i * 100)), D("0.10") if i < 50 else D("0.2475"))
            for i in range(101)
        ]
        result = find_target_points(points, D("0.24"))
        assert result.targets == [D("0"), D("5000"), D("10000")]

    def test_a_narrow_segment_that_only_looks_costly_is_ignored(self):
        # a boundary point seven dollars away: the cost rounds up by a dollar (14% there)
        # and a dollar over a one-dollar gap is 100%, but the points' own rates are low
        points = [
            CostPoint(D("0"), D("0"), D("0.12")),
            CostPoint(D("1000"), D("120"), D("0.12")),
            CostPoint(D("1001"), D("121"), D("0.12")),
            CostPoint(D("2000"), D("240"), D("0.12")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.targets == [D("0"), D("2000")]
        assert len(result.legs) == 1

    def test_a_run_with_no_segment_that_really_costs_more_is_noise(self):
        points = [
            CostPoint(D("0"), D("0"), D("0.30")),
            CostPoint(D("1000"), D("100"), D("0.30")),
            CostPoint(D("2000"), D("200"), D("0.10")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.targets == [D("0"), D("2000")]

    def test_the_target_is_placed_by_the_segment_not_the_looking_ahead_rate(self):
        # the rate looks ahead over a window, so it turns high two points early; the
        # target is the point where the cost really starts to climb
        points = [
            CostPoint(D("0"), D("0"), D("0.10")),
            CostPoint(D("100"), D("10"), D("0.30")),
            CostPoint(D("200"), D("20"), D("0.30")),
            CostPoint(D("300"), D("60"), D("0.40")),
            CostPoint(D("400"), D("100"), D("0.40")),
            CostPoint(D("100000"), D("100"), D("0.00")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.targets == [D("0"), D("200"), D("100000")]
        # the cheap hundreds before the target stay in the first leg
        assert result.legs[0].to_income == D("200")


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
            CostPoint(D("0"), D("0"), D("5000"), ("irmaa",)),
            CostPoint(D("1"), D("5000"), D("5000"), ("aca", "irmaa")),
            CostPoint(D("2"), D("10000"), D("0"), ()),
            CostPoint(D("1000000"), D("10000"), D("0")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.legs[0].causes == ("irmaa", "aca")

    def test_costly_stretch_only_contributes_its_causes(self):
        points = [
            CostPoint(D("0"), D("0"), D("0.10"), ("cheap",)),
            CostPoint(D("1000"), D("100"), D("5.0"), ("irmaa",)),
            CostPoint(D("1001"), D("5100"), D("0.10"), ()),
            CostPoint(D("100000"), D("20000"), D("0.10")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.legs[0].causes == ()
        assert result.legs[1].causes == ("irmaa",)

    def test_looking_ahead_points_before_the_start_do_not_add_causes_to_the_leg_before(self):
        points = [
            CostPoint(D("0"), D("0"), D("0.30"), ("torpedo",)),
            CostPoint(D("100"), D("10"), D("0.30"), ("torpedo",)),
            CostPoint(D("200"), D("60"), D("0.40"), ("torpedo",)),
            CostPoint(D("100000"), D("60"), D("0.00")),
        ]
        result = find_target_points(points, D("0.25"))
        assert result.targets == [D("0"), D("100"), D("100000")]
        assert result.legs[0].causes == ()
