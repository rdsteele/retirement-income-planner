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


# ── Shared API helper script ─────────────────────────────────────────────
#
# Pages that call scenario endpoints rely on js/api.js to turn failed requests
# into visible errors; losing the script tag would silently break that.

_PAGES_USING_API_HELPERS = ["income", "emr", "tax", "scenarios"]


def test_api_helper_script_is_served():
    resp = client.get("/static/js/api.js")
    assert resp.status_code == 200
    assert "function apiRequest" in resp.text
    assert resp.headers["cache-control"] == "no-cache"


def test_pages_load_the_api_helper_script():
    for page in _PAGES_USING_API_HELPERS:
        html = client.get(f"/static/{page}.html").text
        assert '<script src="/static/js/api.js"></script>' in html, page


def test_pages_no_longer_call_scenario_endpoints_with_bare_fetch():
    """Scenario writes must go through the checked helpers."""
    for page in ["income", "emr", "tax"]:
        html = client.get(f"/static/{page}.html").text
        assert "fetch('/api/scenarios" not in html, page
        assert "fetch(`/api/scenarios" not in html, page
