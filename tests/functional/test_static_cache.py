"""Functional tests for static file caching headers."""

import re

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


# ── Shared scripts ───────────────────────────────────────────────────────
#
# Pages depend on the shared scripts in api/static/js. Losing a script tag would
# break a page at load time, so each page's required scripts are asserted here.

_SHARED_SCRIPTS_BY_PAGE = {
    "income": ["api.js", "common.js", "config.js"],
    "emr": ["api.js", "common.js", "config.js"],
    "tax": ["api.js", "common.js", "config.js"],
    "scenarios": ["api.js", "common.js"],
    "accounts": ["common.js"],
}


def test_shared_scripts_are_served_without_caching():
    for script in ("api.js", "common.js", "config.js"):
        resp = client.get(f"/static/js/{script}")
        assert resp.status_code == 200, script
        assert resp.headers["cache-control"] == "no-cache", script


def test_pages_load_the_shared_scripts_they_need():
    for page, scripts in _SHARED_SCRIPTS_BY_PAGE.items():
        html = client.get(f"/static/{page}.html").text
        for script in scripts:
            assert f'<script src="/static/js/{script}"></script>' in html, (page, script)


def test_pages_load_shared_scripts_before_their_own_code():
    for page, scripts in _SHARED_SCRIPTS_BY_PAGE.items():
        html = client.get(f"/static/{page}.html").text
        first_inline = html.index("<script>")
        for script in scripts:
            assert html.index(f'src="/static/js/{script}"') < first_inline, (page, script)


def test_pages_no_longer_call_scenario_endpoints_with_bare_fetch():
    """Scenario writes must go through the checked helpers."""
    for page in ["income", "emr", "tax"]:
        html = client.get(f"/static/{page}.html").text
        assert "fetch('/api/scenarios" not in html, page
        assert "fetch(`/api/scenarios" not in html, page


def test_pages_do_not_redefine_shared_helpers():
    """Shared helpers live in js/ only; a page-level copy would drift."""
    page_level = re.compile(
        r"^  (?:const (?:el|fnum|fmt\$)\b|function (?:escHtml|populateSelect|setField|"
        r"showError|clearError|loadTaxYears)\b)",
        re.MULTILINE,
    )
    for page, scripts in _SHARED_SCRIPTS_BY_PAGE.items():
        html = client.get(f"/static/{page}.html").text
        redefined = page_level.findall(html)
        assert redefined == [], (page, redefined)


def test_emr_and_tax_pages_do_not_classify_withdrawals():
    """Folding withdrawals into income is the server's job (scenario_inputs service)."""
    for page in ["emr", "tax"]:
        html = client.get(f"/static/{page}.html").text
        for token in ("executed_withdrawals", "trad_withdrawals", "tax_deferred", "stcg"):
            assert token not in html, (page, token)
