"""Functional tests for POST /api/target-points.

Uses FastAPI TestClient with real data files — no mocks.
"""

from fastapi.testclient import TestClient

from api.main import app
from services.data_loader import load_config, load_federal_data

client = TestClient(app)

_BASE = {
    "filing_status": "single",
    "tax_year": 2026,
    "pension": 40000.0,
    "pension_taxable": 40000.0,
    "sweep_floor": 0.0,
    "sweep_ceiling": 150000.0,
    "sweep_step": 1000.0,
    "include_ohio": False,
    "include_aca": False,
    "irmaa_inflation_rate": 0.0,
    "max_emr": 0.30,
}


def _post(**overrides):
    return client.post("/api/target-points", json={**_BASE, **overrides})


class TestHappyPath:
    def setup_method(self):
        self.resp = _post()
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_response_shape(self):
        assert set(self.body) == {
            "filing_status",
            "tax_year",
            "max_emr",
            "targets",
            "legs",
            "irmaa_thresholds",
        }
        assert self.body["max_emr"] == 0.30
        assert set(self.body["legs"][0]) == {
            "from_income",
            "to_income",
            "average_emr",
            "cost",
            "causes",
        }

    def test_targets_start_and_end_the_sweep(self):
        assert self.body["targets"][0] == 0.0
        assert self.body["targets"][-1] == 150000.0

    def test_every_leg_is_within_the_maximum(self):
        assert self.body["legs"]
        assert all(leg["average_emr"] <= self.body["max_emr"] for leg in self.body["legs"])

    def test_legs_are_between_targets(self):
        for leg in self.body["legs"]:
            assert leg["from_income"] in self.body["targets"]
            assert leg["to_income"] in self.body["targets"]


class TestOptions:
    def test_irmaa_off_leaves_no_cliff_targets(self):
        body = _post(include_irmaa=False).json()
        assert body["targets"] == [0.0, 150000.0]

    def test_irmaa_on_finds_cliff_targets(self):
        assert len(_post().json()["targets"]) > 2

    def test_withdrawals_move_the_targets(self):
        plain = _post().json()["targets"]
        moved = _post(
            planned_withdrawals=[{"account_type": "traditional", "amount": 10000.0}]
        ).json()["targets"]
        assert moved != plain

    def test_zero_enrollees_means_no_cliff_targets(self):
        assert _post(irmaa_enrollees=0).json()["targets"] == [0.0, 150000.0]

    def test_default_maximum_in_config_is_a_usable_value(self):
        default = load_config()["target_emr_rate_default"]
        assert _post(max_emr=default).status_code == 200


class TestIrmaaThresholds:
    def test_published_thresholds_when_not_inflated(self):
        published = load_federal_data(2026)["irmaa_thresholds"]["single"]
        thresholds = _post(irmaa_inflation_rate=0.0).json()["irmaa_thresholds"]
        assert thresholds == [float(t) for t in published]

    def test_inflation_raises_them_except_the_top_one(self):
        flat = _post(irmaa_inflation_rate=0.0).json()["irmaa_thresholds"]
        grown = _post(irmaa_inflation_rate=0.05).json()["irmaa_thresholds"]
        assert all(g > f for g, f in zip(grown[:-1], flat[:-1]))
        assert grown[-1] == flat[-1]

    def test_the_first_target_before_a_cliff_follows_the_returned_threshold(self):
        # 40,000 of fixed income, so the sweep reaches the threshold at threshold - 40,000
        body = _post(irmaa_inflation_rate=0.05).json()
        assert body["irmaa_thresholds"][0] - 40000.0 in body["targets"]

    def test_none_when_irmaa_is_left_out(self):
        assert _post(include_irmaa=False).json()["irmaa_thresholds"] == []


class TestErrors:
    def test_unsupported_filing_status_is_422(self):
        assert _post(filing_status="bogus").status_code == 422

    def test_unsupported_tax_year_is_422(self):
        assert _post(tax_year=1900).status_code == 422

    def test_too_many_enrollees_is_422(self):
        resp = _post(irmaa_enrollees=5)
        assert resp.status_code == 422
        assert "enrollees" in resp.json()["detail"]

    def test_negative_maximum_is_rejected(self):
        assert _post(max_emr=-0.1).status_code == 422

    def test_missing_maximum_is_rejected(self):
        body = {k: v for k, v in _BASE.items() if k != "max_emr"}
        assert client.post("/api/target-points", json=body).status_code == 422
