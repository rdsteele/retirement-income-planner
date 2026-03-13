"""Functional tests for GET /api/tax-years.

Uses FastAPI TestClient with real bracket data — no mocks.
"""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_returns_correct_years():
    resp = client.get("/api/tax-years")
    assert resp.status_code == 200
    data = resp.json()
    assert 2025 in data["years"]
    assert 2026 in data["years"]


def test_default_year_is_highest():
    resp = client.get("/api/tax-years")
    data = resp.json()
    assert data["default_year"] == max(data["years"])


def test_response_shape():
    resp = client.get("/api/tax-years")
    data = resp.json()
    assert "years" in data
    assert "default_year" in data
    assert isinstance(data["years"], list)
    assert isinstance(data["default_year"], int)
    assert all(isinstance(y, int) for y in data["years"])
    assert data["years"] == sorted(data["years"])
