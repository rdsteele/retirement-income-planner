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
    current_file  = tmp_path / "current_scenario.json"

    _list        = svc.list_scenarios
    _load        = svc.load_scenario
    _save        = svc.save_scenario
    _delete      = svc.delete_scenario
    _get_current = svc.get_current_scenario
    _set_current = svc.set_current_scenario

    monkeypatch.setattr(svc, "list_scenarios",
        lambda _scenarios_dir=scenarios_dir: _list(_scenarios_dir))
    monkeypatch.setattr(svc, "load_scenario",
        lambda name, _scenarios_dir=scenarios_dir: _load(name, _scenarios_dir))
    monkeypatch.setattr(svc, "save_scenario",
        lambda name, data, _scenarios_dir=scenarios_dir: _save(name, data, _scenarios_dir))
    monkeypatch.setattr(svc, "delete_scenario",
        lambda name, _scenarios_dir=scenarios_dir: _delete(name, _scenarios_dir))
    monkeypatch.setattr(svc, "get_current_scenario",
        lambda _current_file=current_file: _get_current(_current_file))
    monkeypatch.setattr(svc, "set_current_scenario",
        lambda name, _current_file=current_file: _set_current(name, _current_file))


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
