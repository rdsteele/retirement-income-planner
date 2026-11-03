"""Functional tests for static file caching headers."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_static_pages_must_revalidate():
    resp = client.get("/static/income.html")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"


def test_conditional_request_returns_not_modified():
    first = client.get("/static/income.html")
    second = client.get("/static/income.html", headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304
    assert second.headers["cache-control"] == "no-cache"
