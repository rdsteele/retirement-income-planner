"""Unit tests for services.irmaa: data and config lookups are replaced."""

from decimal import Decimal

import pytest

import services.irmaa as module

D = Decimal
_THRESHOLDS = {"single": ["100000", "140000", "500000"], "mfj": ["200000", "280000", "750000"]}
_DATA = {
    "threshold_rounding": "1000",
    "index_top_threshold": False,
    "monthly_surcharge": {
        "part_b": ["80.00", "200.00", "500.00"],
        "part_d": ["15.00", "40.00", "90.00"],
    },
}
_FILERS = {"single": 1, "mfj": 2}


@pytest.fixture(autouse=True)
def _stub_data(monkeypatch):
    monkeypatch.setattr(module, "load_federal_data", lambda year: {"irmaa_thresholds": _THRESHOLDS})
    monkeypatch.setattr(module, "load_irmaa_data", lambda year: _DATA)
    monkeypatch.setattr(module, "filer_count", lambda status: _FILERS[status])
    monkeypatch.setattr(module, "get_irmaa_lookback_years", lambda: 2)


def _surcharge(magi, status="single", enrollees=1, rate="0"):
    return module.annual_surcharge(
        D(magi), filing_status=status, tax_year=0, enrollees=enrollees, inflation_rate=D(rate)
    )


class TestTier:
    thresholds = [D("100000"), D("140000"), D("500000")]

    def test_at_a_threshold_is_the_lower_tier(self):
        assert module.irmaa_tier(D("100000"), self.thresholds) == 0

    def test_one_dollar_above_a_threshold_is_the_next_tier(self):
        assert module.irmaa_tier(D("100001"), self.thresholds) == 1

    def test_between_thresholds(self):
        assert module.irmaa_tier(D("150000"), self.thresholds) == 2

    def test_top_tier_starts_at_its_threshold(self):
        assert module.irmaa_tier(D("499999"), self.thresholds) == 2
        assert module.irmaa_tier(D("500000"), self.thresholds) == 3


class TestMonthlySurcharge:
    def test_no_surcharge_at_tier_zero(self):
        assert module.monthly_surcharge_per_person(0, 0) == D("0")

    def test_part_b_and_part_d_are_added(self):
        assert module.monthly_surcharge_per_person(1, 0) == D("95.00")
        assert module.monthly_surcharge_per_person(3, 0) == D("590.00")


class TestProjectedThresholds:
    def test_zero_rate_returns_published_thresholds(self):
        assert module.projected_thresholds("single", 0, D("0")) == [
            D("100000"),
            D("140000"),
            D("500000"),
        ]

    def test_grows_over_the_lookback_and_rounds_to_the_unit(self):
        # 100,000 x 1.05^2 = 110,250 -> 110,000; 140,000 x 1.05^2 = 154,350 -> 154,000
        grown = module.projected_thresholds("single", 0, D("0.05"))
        assert grown[:2] == [D("110000"), D("154000")]

    def test_top_threshold_is_not_indexed_when_the_file_says_so(self):
        assert module.projected_thresholds("single", 0, D("0.05"))[-1] == D("500000")

    def test_top_threshold_grows_when_the_file_indexes_it(self, monkeypatch):
        monkeypatch.setattr(
            module, "load_irmaa_data", lambda year: {**_DATA, "index_top_threshold": True}
        )
        assert module.projected_thresholds("single", 0, D("0.05"))[-1] == D("551000")

    def test_rounds_half_up(self, monkeypatch):
        # 100,000 x 1.05^2 = 110,250 with a unit of 500 sits on 110,500 / 110,000: 220.5 -> 221
        monkeypatch.setattr(
            module, "load_irmaa_data", lambda year: {**_DATA, "threshold_rounding": "500"}
        )
        assert module.projected_thresholds("single", 0, D("0.05"))[0] == D("110500")


class TestAnnualSurcharge:
    def test_zero_below_the_first_threshold(self):
        assert _surcharge("100000") == D("0")

    def test_whole_year_lands_on_the_first_dollar_above(self):
        assert _surcharge("100001") == D("95.00") * 12

    def test_scales_with_enrollees(self):
        assert _surcharge("100001", "mfj", 2, "0") == D("0")  # mfj tier starts at 200,000
        assert _surcharge("200001", "mfj", 2) == D("95.00") * 12 * 2
        assert _surcharge("200001", "mfj", 1) == D("95.00") * 12

    def test_zero_enrollees_pay_nothing(self):
        assert _surcharge("600000", "mfj", 0) == D("0")

    def test_inflation_moves_the_threshold(self):
        # threshold grows to 110,000, so 105,000 is no longer above it
        assert _surcharge("105000", rate="0.05") == D("0")
        assert _surcharge("111000", rate="0.05") == D("95.00") * 12

    def test_too_many_enrollees_is_rejected(self):
        with pytest.raises(ValueError, match="enrollees"):
            _surcharge("150000", "single", 2)

    def test_negative_enrollees_is_rejected(self):
        with pytest.raises(ValueError, match="enrollees"):
            _surcharge("150000", "single", -1)


def test_default_enrollees_is_everyone_on_the_return():
    assert module.default_enrollees("single") == 1
    assert module.default_enrollees("mfj") == 2
