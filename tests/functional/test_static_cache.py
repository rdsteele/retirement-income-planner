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
    "income": ["api.js", "common.js", "config.js", "scenario-bar.js"],
    "emr": ["api.js", "common.js", "config.js", "scenario-bar.js"],
    "tax": ["api.js", "common.js", "config.js", "scenario-bar.js"],
    "scenarios": ["api.js", "common.js", "scenario-bar.js"],
    "accounts": ["common.js"],
}
_PAGES_WITH_SCENARIO_BAR = ["income", "emr", "tax", "scenarios"]


def test_shared_scripts_are_served_without_caching():
    for script in ("api.js", "common.js", "config.js", "scenario-bar.js"):
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
        r"^  (?:const (?:el|fnum|fmt\$|SCENARIO_FORMAT_VERSION)\b|let currentScenarioName\b|"
        r"(?:async )?function (?:escHtml|populateSelect|setField|showError|clearError|loadTaxYears|"
        r"updateScenarioBar|setScenarioStatus|loadCurrentScenario|saveCurrentScenario|"
        r"saveAsScenario|buildScenarioData|newEmptyScenario)\b)",
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


def test_scenario_bar_stylesheet_is_served_and_linked():
    resp = client.get("/static/css/scenario-bar.css")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
    for page in _PAGES_WITH_SCENARIO_BAR:
        html = client.get(f"/static/{page}.html").text
        assert '<link rel="stylesheet" href="/static/css/scenario-bar.css">' in html, page


def test_pages_do_not_carry_their_own_scenario_bar_styles():
    for page in _PAGES_WITH_SCENARIO_BAR:
        html = client.get(f"/static/{page}.html").text
        assert ".scenario-btn {" not in html, page
        assert ".scenario-name {" not in html, page


def test_pages_that_show_a_scenario_status_have_the_status_element():
    for page in ["income", "emr", "tax"]:
        html = client.get(f"/static/{page}.html").text
        assert 'id="scenario-status"' in html, page


def test_scenarios_page_has_no_inert_save_buttons():
    html = client.get("/static/scenarios.html").text
    assert 'id="save-btn"' not in html
    assert 'id="save-as-btn"' not in html
