"""Unit tests for calculate_target_points: the total cost sweep is replaced."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

import services.target_points as module
from services.income_inputs import IncomeInputs

D = Decimal
_ZERO = D("0")


def _point(income, *, tax="0", aca="0", irmaa="0", total="0", **emr):
    components = dict(
        emr_ordinary=_ZERO,
        emr_ss_torpedo=_ZERO,
        emr_pref_stacking=_ZERO,
        emr_niit=_ZERO,
        emr_aca=_ZERO,
        emr_irmaa=_ZERO,
    )
    components.update({k: D(v) for k, v in emr.items()})
    return SimpleNamespace(
        income=D(income),
        total_tax=D(tax),
        aca_subsidy_loss=D(aca),
        irmaa_surcharge=D(irmaa),
        total_cost_emr=D(total),
        **components,
    )


class TestToCostPoints:
    def test_cost_adds_tax_lost_subsidy_and_surcharge(self):
        points = module.to_cost_points([_point("100", tax="10", aca="20", irmaa="30")], D("0.25"))
        assert points[0].cost == D("60")
        assert points[0].income == D("100")

    def test_rate_is_the_total_cost_emr_at_the_point(self):
        points = module.to_cost_points([_point("0", total="0.31")], D("0.25"))
        assert points[0].rate == D("0.31")

    def test_each_active_component_becomes_a_cause(self):
        point = _point(
            "0",
            emr_ss_torpedo="0.1",
            emr_pref_stacking="0.1",
            emr_niit="0.038",
            emr_aca="0.2",
            emr_irmaa="1",
        )
        assert module.to_cost_points([point], D("0.25"))[0].causes == (
            "ss_torpedo",
            "pref_stacking",
            "niit",
            "aca",
            "irmaa",
        )

    def test_ordinary_rate_is_a_cause_only_above_the_maximum(self):
        point = _point("0", emr_ordinary="0.32")
        assert module.to_cost_points([point], D("0.25"))[0].causes == ("bracket",)
        assert module.to_cost_points([point], D("0.35"))[0].causes == ()

    def test_no_active_component_means_no_cause(self):
        assert module.to_cost_points([_point("0")], D("0.25"))[0].causes == ()


class TestCalculateTargetPoints:
    def test_runs_the_sweep_with_the_options_and_searches_its_points(self, monkeypatch):
        seen = {}

        def fake_total_cost(**kwargs):
            seen.update(kwargs)
            return SimpleNamespace(
                points=[_point("0"), _point("1000", tax="100"), _point("2000", tax="200")],
                irmaa_projected_thresholds=[D("115000"), D("144000")],
            )

        monkeypatch.setattr(module, "calculate_total_cost", fake_total_cost)
        result = module.calculate_target_points(
            income=IncomeInputs(),
            filing_status="single",
            tax_year=1,
            max_rate=D("0.25"),
            include_aca=True,
            irmaa_enrollees=1,
            irmaa_inflation_rate=D("0.03"),
        )
        assert seen["include_irmaa"] is True
        assert seen["include_aca"] is True
        assert seen["irmaa_enrollees"] == 1
        assert seen["irmaa_inflation_rate"] == D("0.03")
        assert result.targets == [D("0"), D("2000")]
        assert result.legs[0].average_emr == D("0.1000")
        assert result.irmaa_thresholds == [D("115000"), D("144000")]

    def test_thresholds_are_still_reported_for_the_growth_when_irmaa_is_off(self, monkeypatch):
        monkeypatch.setattr(
            module,
            "calculate_total_cost",
            lambda **kwargs: SimpleNamespace(points=[], irmaa_projected_thresholds=[]),
        )
        seen = {}

        def fake_projected(status, year, rate):
            seen.update(status=status, year=year, rate=rate)
            return [D("123000")]

        monkeypatch.setattr(module, "projected_thresholds", fake_projected)
        result = module.calculate_target_points(
            income=IncomeInputs(),
            filing_status="single",
            tax_year=7,
            max_rate=D("0.25"),
            include_irmaa=False,
            irmaa_inflation_rate=D("0.04"),
        )
        assert result.irmaa_thresholds == [D("123000")]
        assert seen == {"status": "single", "year": 7, "rate": D("0.04")}

    def test_default_growth_applies_to_the_reported_thresholds_when_none_is_given(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            module,
            "calculate_total_cost",
            lambda **kwargs: SimpleNamespace(points=[], irmaa_projected_thresholds=[]),
        )
        monkeypatch.setattr(module, "get_irmaa_inflation_default", lambda: D("0.02"))
        rates = []
        monkeypatch.setattr(
            module, "projected_thresholds", lambda s, y, rate: rates.append(rate) or []
        )
        module.calculate_target_points(
            income=IncomeInputs(),
            filing_status="single",
            tax_year=7,
            max_rate=D("0.25"),
            include_irmaa=False,
        )
        assert rates == [D("0.02")]

    def test_irmaa_can_be_turned_off(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            module,
            "calculate_total_cost",
            lambda **kwargs: (
                seen.update(kwargs) or SimpleNamespace(points=[], irmaa_projected_thresholds=[])
            ),
        )
        monkeypatch.setattr(module, "projected_thresholds", lambda *args: [])
        module.calculate_target_points(
            income=IncomeInputs(),
            filing_status="single",
            tax_year=1,
            max_rate=D("0.25"),
            include_irmaa=False,
        )
        assert seen["include_irmaa"] is False

    def test_a_negative_maximum_is_rejected(self, monkeypatch):
        monkeypatch.setattr(
            module,
            "calculate_total_cost",
            lambda **kwargs: SimpleNamespace(points=[], irmaa_projected_thresholds=[]),
        )
        with pytest.raises(ValueError, match="negative"):
            module.calculate_target_points(
                income=IncomeInputs(), filing_status="single", tax_year=1, max_rate=D("-1")
            )
