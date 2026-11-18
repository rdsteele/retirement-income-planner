"""Unit tests for the IRMAA part of services/total_cost.py.

Real data files are used: a household with fixed pension income and an ordinary sweep that
climbs through several IRMAA tiers. Thresholds and surcharge amounts are read from the data
files, never copied here.
"""

from decimal import Decimal

import pytest

from services.data_loader import load_federal_data, load_irmaa_data
from services.emr import SweepMode
from services.income_inputs import IncomeInputs
from services.irmaa import irmaa_tier, projected_thresholds
from services.total_cost import calculate_total_cost

D = Decimal
_YEAR = 2026
_STATUS = "single"
_MONTHS = D("12")


def _run(*, income=None, status=_STATUS, ceiling="150000", **kwargs):
    return calculate_total_cost(
        income=income or IncomeInputs(pension=D("80000")),
        filing_status=status,
        tax_year=_YEAR,
        sweep_mode=SweepMode.ORDINARY,
        sweep_floor=D("0"),
        sweep_ceiling=D(ceiling),
        sweep_step=D("1000"),
        **kwargs,
    )


def _thresholds(status=_STATUS):
    return [D(t) for t in load_federal_data(_YEAR)["irmaa_thresholds"][status]]


def _monthly(tier):
    amounts = load_irmaa_data(_YEAR)["monthly_surcharge"]
    return sum(D(amounts[part][tier - 1]) for part in amounts)


def _cliff_pairs(result):
    """Adjacent points where the surcharge rises."""
    pts = result.points
    return [(a, b) for a, b in zip(pts, pts[1:]) if b.irmaa_surcharge > a.irmaa_surcharge]


class TestOff:
    def test_no_surcharge_by_default(self):
        result = _run()
        assert all(p.irmaa_surcharge == D("0") for p in result.points)
        assert all(p.emr_irmaa == D("0") for p in result.points)
        assert result.irmaa_projected_thresholds == []

    def test_total_cost_emr_is_unchanged_by_default(self):
        result = _run()
        assert all(p.total_cost_emr == p.emr for p in result.points)


class TestSurcharge:
    def test_each_point_pays_its_tier(self):
        result = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        for p in result.points:
            tier = irmaa_tier(p.irmaa_magi, _thresholds())
            assert p.irmaa_surcharge == (_monthly(tier) * _MONTHS if tier else D("0"))

    def test_cliff_amount_is_the_whole_year_of_part_b_and_part_d(self):
        result = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        low, high = _cliff_pairs(result)[0]
        assert high.irmaa_surcharge - low.irmaa_surcharge == _monthly(1) * _MONTHS

    def test_one_cliff_per_threshold_the_sweep_crosses(self):
        result = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        crossed = [t for t in _thresholds() if t < result.points[-1].irmaa_magi]
        assert len(_cliff_pairs(result)) == len(crossed)


class TestBoundaryPoints:
    def test_last_point_before_a_cliff_sits_exactly_at_the_threshold(self):
        result = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        low, high = _cliff_pairs(result)[0]
        assert low.irmaa_magi == _thresholds()[0]
        assert high.irmaa_magi > _thresholds()[0]

    def test_cliff_points_are_one_dollar_apart(self):
        result = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        low, high = _cliff_pairs(result)[0]
        assert high.income - low.income == D("1")

    def test_cliff_is_found_inside_the_social_security_torpedo(self):
        # Taxable Social Security makes MAGI rise faster than the sweep, so the
        # threshold cannot be solved by subtraction.
        income = IncomeInputs(pension=D("60000"), ss_benefit=D("30000"))
        result = _run(income=income, include_irmaa=True, irmaa_inflation_rate=D("0"))
        low, high = _cliff_pairs(result)[0]
        assert low.irmaa_magi <= _thresholds()[0] < high.irmaa_magi

    def test_nothing_added_when_the_sweep_never_reaches_a_threshold(self):
        result = _run(ceiling="10000", include_irmaa=True)
        assert _cliff_pairs(result) == []

    def test_nothing_added_when_the_sweep_starts_above_every_threshold(self):
        income = IncomeInputs(pension=max(_thresholds()) + D("1000"))
        result = _run(income=income, ceiling="5000", include_irmaa=True)
        assert _cliff_pairs(result) == []


class TestEmrSpike:
    def test_spike_sits_on_the_last_cheap_point_only(self):
        result = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        low, high = _cliff_pairs(result)[0]
        assert low.emr_irmaa == _monthly(1) * _MONTHS / D("1000")
        spiking = [p for p in result.points if p.emr_irmaa != D("0")]
        assert len(spiking) == len(_cliff_pairs(result))

    def test_total_cost_emr_includes_the_spike(self):
        result = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        low, _ = _cliff_pairs(result)[0]
        assert low.total_cost_emr == low.emr + low.emr_irmaa


class TestEnrolleesAndInflation:
    def test_default_enrollees_is_everyone_on_the_return(self):
        joint = _run(
            income=IncomeInputs(pension=D("150000")),
            status="mfj",
            ceiling="200000",
            include_irmaa=True,
            irmaa_inflation_rate=D("0"),
        )
        one = _run(
            income=IncomeInputs(pension=D("150000")),
            status="mfj",
            ceiling="200000",
            include_irmaa=True,
            irmaa_enrollees=1,
            irmaa_inflation_rate=D("0"),
        )
        assert joint.points[-1].irmaa_surcharge == one.points[-1].irmaa_surcharge * 2

    def test_zero_enrollees_means_no_surcharge_and_no_cliff(self):
        result = _run(include_irmaa=True, irmaa_enrollees=0, irmaa_inflation_rate=D("0"))
        assert all(p.irmaa_surcharge == D("0") for p in result.points)

    def test_too_many_enrollees_is_rejected(self):
        with pytest.raises(ValueError, match="enrollees"):
            _run(include_irmaa=True, irmaa_enrollees=2)

    def test_inflation_moves_the_cliff_up(self):
        flat = _run(include_irmaa=True, irmaa_inflation_rate=D("0"))
        grown = _run(include_irmaa=True, irmaa_inflation_rate=D("0.10"))
        flat_low, _ = _cliff_pairs(flat)[0]
        grown_low, _ = _cliff_pairs(grown)[0]
        assert grown_low.income > flat_low.income
        assert grown.irmaa_projected_thresholds == projected_thresholds(_STATUS, _YEAR, D("0.10"))


class TestWithAca:
    def test_aca_and_irmaa_can_both_be_on(self):
        result = _run(
            income=IncomeInputs(pension=D("30000")),
            include_aca=True,
            include_irmaa=True,
            irmaa_inflation_rate=D("0"),
        )
        assert any(p.aca_subsidy_loss != D("0") for p in result.points)
        assert _cliff_pairs(result)
