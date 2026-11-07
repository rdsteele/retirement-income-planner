"""Functional tests for GET /api/config.

Uses FastAPI TestClient with real config.json — no mocks.
"""

from fastapi.testclient import TestClient

import services.data_loader as loader
from api.main import app
from services.data_loader import supported_filing_statuses

client = TestClient(app)


def test_returns_correct_values():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["irmaa_inflation_default"] == 0.025
    assert data["y_axis_max_emr"] == 0.50
    assert data["sweep_step_default"] == 100


def test_response_shape():
    resp = client.get("/api/config")
    data = resp.json()
    assert "irmaa_inflation_default" in data
    assert "y_axis_max_emr" in data
    assert "sweep_step_default" in data
    numeric = ["irmaa_inflation_default", "y_axis_max_emr", "sweep_step_default"]
    assert all(isinstance(data[k], float) for k in numeric)


def test_returns_ui_settings_from_config():
    data = client.get("/api/config").json()
    assert isinstance(data["irmaa_lookback_years"], int)
    assert data["irmaa_lookback_years"] > 0
    assert data["income_plan_sweep_ceiling"] > 0


def test_returns_filing_statuses_for_dropdowns():
    statuses = client.get("/api/config").json()["filing_statuses"]
    assert statuses
    assert all(set(s) == {"value", "label", "filers"} for s in statuses)
    assert [s["value"] for s in statuses] == supported_filing_statuses()


def test_missing_config_returns_500(monkeypatch, tmp_path):
    monkeypatch.setattr(loader, "_CONFIG_PATH", tmp_path / "nonexistent.json")
    loader.load_config.cache_clear()
    try:
        resp = client.get("/api/config")
    finally:
        loader.load_config.cache_clear()
    assert resp.status_code == 500
    assert "config.json" in resp.json()["detail"]


def test_root_redirects_to_income():
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302, 307, 308)
    assert "/static/income.html" in resp.headers["location"]


def test_emr_redirects_to_emr():
    resp = client.get("/emr", follow_redirects=False)
    assert resp.status_code in (301, 302, 307, 308)
    assert "/static/emr.html" in resp.headers["location"]
