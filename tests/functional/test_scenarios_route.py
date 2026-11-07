"""Functional tests for the scenarios API routes.

Uses FastAPI TestClient. All file I/O is redirected to tmp_path —
no test touches profile/scenarios/ or profile/current_scenario.json.
"""

import pytest
from fastapi.testclient import TestClient

import services.scenarios as svc
from api.main import app

client = TestClient(app)

_SCENARIO_DATA = {
    "name": "Test Plan",
    "saved_at": "2026-03-16T12:00:00",
    "version": "1.0",
    "inputs": {"pension": 1000},
}


# ── Isolation fixture ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolate_storage(tmp_path, monkeypatch):
    """Redirect every service call to a fresh temp directory per test."""
    scenarios_dir = tmp_path / "scenarios"
    current_file = tmp_path / "current_scenario.json"

    _list = svc.list_scenarios
    _load = svc.load_scenario
    _save = svc.save_scenario
    _delete = svc.delete_scenario
    _get_current = svc.get_current_scenario
    _set_current = svc.set_current_scenario

    monkeypatch.setattr(
        svc, "list_scenarios", lambda _scenarios_dir=scenarios_dir: _list(_scenarios_dir)
    )
    monkeypatch.setattr(
        svc, "load_scenario", lambda name, _scenarios_dir=scenarios_dir: _load(name, _scenarios_dir)
    )
    monkeypatch.setattr(
        svc,
        "save_scenario",
        lambda name, data, _scenarios_dir=scenarios_dir: _save(name, data, _scenarios_dir),
    )
    monkeypatch.setattr(
        svc,
        "delete_scenario",
        lambda name, _scenarios_dir=scenarios_dir: _delete(name, _scenarios_dir),
    )
    monkeypatch.setattr(
        svc, "get_current_scenario", lambda _current_file=current_file: _get_current(_current_file)
    )
    monkeypatch.setattr(
        svc,
        "set_current_scenario",
        lambda name, _current_file=current_file: _set_current(name, _current_file),
    )


# ---------------------------------------------------------------------------
# 1. GET /api/scenarios returns empty list when no scenarios saved
# ---------------------------------------------------------------------------


def test_list_scenarios_empty() -> None:
    resp = client.get("/api/scenarios")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 2. POST /api/scenarios/{name} saves; GET /api/scenarios/{name} returns same
# ---------------------------------------------------------------------------


def test_save_then_load_via_api() -> None:
    resp = client.post("/api/scenarios/Test Plan", json=_SCENARIO_DATA)
    assert resp.status_code == 200

    resp2 = client.get("/api/scenarios/Test Plan")
    assert resp2.status_code == 200
    assert resp2.json() == _SCENARIO_DATA


# ---------------------------------------------------------------------------
# 3. DELETE /api/scenarios/{name} returns 204
# ---------------------------------------------------------------------------


def test_delete_returns_204() -> None:
    client.post("/api/scenarios/Test Plan", json=_SCENARIO_DATA)
    resp = client.delete("/api/scenarios/Test Plan")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# 4. DELETE /api/scenarios/{name} returns 404 for missing scenario
# ---------------------------------------------------------------------------


def test_delete_missing_returns_404() -> None:
    resp = client.delete("/api/scenarios/Nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. GET /api/scenarios/current returns null when none set
# ---------------------------------------------------------------------------


def test_get_current_returns_null_when_unset() -> None:
    resp = client.get("/api/scenarios/current")
    assert resp.status_code == 200
    assert resp.json()["name"] is None


# ---------------------------------------------------------------------------
# 6. POST /api/scenarios/current sets name; GET returns it
# ---------------------------------------------------------------------------


def test_set_then_get_current() -> None:
    client.post("/api/scenarios/current", json={"name": "2026 Base Plan"})
    resp = client.get("/api/scenarios/current")
    assert resp.status_code == 200
    assert resp.json()["name"] == "2026 Base Plan"


# ---------------------------------------------------------------------------
# 7. /api/scenarios/current is registered before /{name} — no routing conflict
# ---------------------------------------------------------------------------


def test_current_route_not_treated_as_name_param() -> None:
    """GET /api/scenarios/current must NOT be interpreted as GET /{name}='current'."""
    resp = client.get("/api/scenarios/current")
    assert resp.status_code == 200
    # Would be 404 if "current" were treated as a name with no saved scenario
    body = resp.json()
    assert "name" in body


# ---------------------------------------------------------------------------
# Error branches — each route's except handler returns the correct HTTP status
# ---------------------------------------------------------------------------


def test_list_scenarios_500(monkeypatch) -> None:
    def boom():
        raise Exception("disk error")

    monkeypatch.setattr(svc, "list_scenarios", boom)
    resp = client.get("/api/scenarios")
    assert resp.status_code == 500


def test_get_current_500(monkeypatch) -> None:
    def boom():
        raise Exception("disk error")

    monkeypatch.setattr(svc, "get_current_scenario", boom)
    resp = client.get("/api/scenarios/current")
    assert resp.status_code == 500


def test_set_current_500(monkeypatch) -> None:
    def boom(name):
        raise Exception("disk error")

    monkeypatch.setattr(svc, "set_current_scenario", boom)
    resp = client.post("/api/scenarios/current", json={"name": "plan"})
    assert resp.status_code == 500


def test_get_scenario_404(monkeypatch) -> None:
    def boom(name):
        raise ValueError(f"Scenario not found: {name!r}")

    monkeypatch.setattr(svc, "load_scenario", boom)
    resp = client.get("/api/scenarios/Missing")
    assert resp.status_code == 404


def test_get_scenario_500(monkeypatch) -> None:
    def boom(name):
        raise Exception("disk error")

    monkeypatch.setattr(svc, "load_scenario", boom)
    resp = client.get("/api/scenarios/AnyName")
    assert resp.status_code == 500


def test_post_scenario_500(monkeypatch) -> None:
    def boom(name, data):
        raise Exception("disk error")

    monkeypatch.setattr(svc, "save_scenario", boom)
    resp = client.post("/api/scenarios/AnyName", json=_SCENARIO_DATA)
    assert resp.status_code == 500


def test_delete_scenario_500(monkeypatch) -> None:
    def boom(name):
        raise Exception("disk error")

    monkeypatch.setattr(svc, "delete_scenario", boom)
    resp = client.delete("/api/scenarios/AnyName")
    assert resp.status_code == 500


# ── GET /api/scenarios/{name}/sweep-inputs ───────────────────────────────

_PLAN_WITH_WITHDRAWALS = {
    "name": "Withdrawals",
    "saved_at": "2026-03-16T12:00:00",
    "version": "1.0",
    "inputs": {
        "pension_taxable": 1600,
        "wages": 500,
        "ira_distributions": 2000,
        "fixed_ltcg": 1000,
        "other_investment_ordinary": 300,
    },
    "income_planning": {
        "trad_withdrawals": [{"id": "t", "amount": 10000}],
        "withdrawals": [{"id": "h", "amount": 8000, "basis": 3000}],
        "executed_withdrawals": [
            {"type": "tax_deferred", "amount": 4000},
            {"type": "stcg", "amount": 5000, "basis": 2000},
            {"type": "ltcg", "amount": 6000, "basis": 4000},
        ],
    },
}


class TestSweepInputs:
    def _inputs(self, scenario):
        client.post(f"/api/scenarios/{scenario['name']}", json=scenario)
        resp = client.get(f"/api/scenarios/{scenario['name']}/sweep-inputs")
        assert resp.status_code == 200
        return resp.json()

    def test_returns_all_assembled_fields(self):
        body = self._inputs(_PLAN_WITH_WITHDRAWALS)
        assert set(body) == {
            "pension",
            "wages",
            "interest",
            "ordinary_dividends",
            "qualified_dividends",
            "ira_distributions",
            "other_investment_ordinary",
            "ss_benefit",
            "fixed_ltcg",
            "tax_exempt_interest",
            "above_the_line_adjustments",
            "additional_deductions",
            "taxpayer_65_plus",
            "spouse_65_plus",
        }

    def test_withdrawals_are_folded_into_income(self):
        body = self._inputs(_PLAN_WITH_WITHDRAWALS)
        assert body["ira_distributions"] == 16000.0  # 2000 + 10000 + 4000
        assert body["other_investment_ordinary"] == 3300.0  # 300 + 3000 short-term gain
        assert body["fixed_ltcg"] == 8000.0  # 1000 + 5000 + 2000

    def test_forced_income_passes_through(self):
        body = self._inputs(_PLAN_WITH_WITHDRAWALS)
        assert body["pension"] == 1600.0
        assert body["wages"] == 500.0

    def test_scenario_without_planning_data_uses_inputs_only(self):
        body = self._inputs(_SCENARIO_DATA)
        assert body["pension"] == 0.0  # only gross "pension" is stored; taxable is not
        assert body["ira_distributions"] == 0.0

    def test_unknown_scenario_returns_404(self):
        resp = client.get("/api/scenarios/Nope/sweep-inputs")
        assert resp.status_code == 404

    def test_route_does_not_shadow_the_scenario_route(self):
        client.post("/api/scenarios/Test Plan", json=_SCENARIO_DATA)
        assert client.get("/api/scenarios/Test Plan").json()["name"] == "Test Plan"

    def test_malformed_amount_returns_422(self):
        bad = {**_PLAN_WITH_WITHDRAWALS, "name": "Bad", "inputs": {"interest": "abc"}}
        client.post("/api/scenarios/Bad", json=bad)
        assert client.get("/api/scenarios/Bad/sweep-inputs").status_code == 422
