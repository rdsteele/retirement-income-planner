"""Functional tests for POST /api/tax.

Uses FastAPI TestClient with real bracket data — no mocks.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# Minimal single-filer base request (2026, no SS, no Ohio)
_BASE = {
    "pension": 40000.0,
    "filing_status": "single",
    "tax_year": 2026,
}


# ── 1. Happy path — response shape ───────────────────────────────────────

class TestResponseShape:
    def setup_method(self):
        self.resp = client.post("/api/tax", json=_BASE)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_top_level_fields(self):
        assert self.body["filing_status"] == "single"
        assert self.body["tax_year"] == 2026
        assert "inputs_summary" in self.body
        assert "federal" in self.body
        assert "ohio" in self.body
        assert "summary" in self.body

    def test_inputs_summary_fields_present(self):
        s = self.body["inputs_summary"]
        for key in ("gross_ordinary_income", "ss_taxable", "above_the_line_adjustments",
                    "agi", "standard_deduction", "additional_deductions",
                    "taxable_ordinary", "taxable_preferential"):
            assert key in s, f"missing inputs_summary.{key}"

    def test_federal_fields_present(self):
        f = self.body["federal"]
        for key in ("ordinary_income_tax", "preferential_income_tax", "total_tax",
                    "effective_rate", "marginal_bracket_rate",
                    "bracket_breakdown", "preferential_breakdown"):
            assert key in f, f"missing federal.{key}"

    def test_summary_fields_present(self):
        s = self.body["summary"]
        for key in ("total_federal_tax", "total_ohio_tax", "total_tax",
                    "overall_effective_rate"):
            assert key in s, f"missing summary.{key}"

    def test_bracket_breakdown_at_least_one_row(self):
        assert len(self.body["federal"]["bracket_breakdown"]) >= 1

    def test_pref_breakdown_at_least_one_row(self):
        assert len(self.body["federal"]["preferential_breakdown"]) >= 1

    def test_bracket_row_has_required_keys(self):
        row = self.body["federal"]["bracket_breakdown"][0]
        for key in ("rate", "from", "to", "income_taxed", "tax_amount"):
            assert key in row, f"missing bracket key: {key}"


# ── 2. Ohio included ──────────────────────────────────────────────────────

class TestOhioIncluded:
    def setup_method(self):
        payload = {
            "pension": 40000.0,
            "filing_status": "single",
            "tax_year": 2025,
            "include_ohio": True,
            "ohio_qualifying_retirement_income": 20000.0,
        }
        self.body = client.post("/api/tax", json=payload).json()

    def test_ohio_included_true(self):
        assert self.body["ohio"]["included"] is True

    def test_ohio_fields_populated(self):
        ohio = self.body["ohio"]
        for key in ("ohio_agi", "personal_exemption", "medical_deduction",
                    "ohio_tax_base", "tax_before_credits", "retirement_income_credit",
                    "ohio_tax", "effective_rate"):
            assert ohio[key] is not None, f"ohio.{key} is None"

    def test_ohio_agi_correct(self):
        # total_ordinary = 40000 (pension, no SS, no adjustments)
        # federal_agi = 40000; ohio_agi = 40000 - 0 (ss_taxable) = 40000
        assert self.body["ohio"]["ohio_agi"] == pytest.approx(40000.0)

    def test_ohio_tax_nonzero(self):
        assert self.body["ohio"]["ohio_tax"] == pytest.approx(460.0)

    def test_summary_ohio_tax_populated(self):
        assert self.body["summary"]["total_ohio_tax"] == pytest.approx(460.0)


# ── 3. SS taxability ──────────────────────────────────────────────────────

class TestSSTaxability:
    def setup_method(self):
        # single, 2026; pension=30000, ss_benefit=24000
        # agi_excluding_ss = 30000; prov_income = 30000 + 12000 = 42000 → 85% tier
        # ss_taxable = min(0.85*24000, ...) = 11300 (verified above)
        payload = {
            "pension": 30000.0,
            "ss_benefit": 24000.0,
            "filing_status": "single",
            "tax_year": 2026,
        }
        self.body = client.post("/api/tax", json=payload).json()

    def test_ss_taxable_nonzero(self):
        assert self.body["inputs_summary"]["ss_taxable"] > 0

    def test_ss_taxable_correct(self):
        assert self.body["inputs_summary"]["ss_taxable"] == pytest.approx(11300.0)

    def test_ss_included_in_agi(self):
        s = self.body["inputs_summary"]
        # agi = gross_ordinary + ss_taxable + pref - above_the_line
        # gross_ordinary = 30000, ss_taxable = 11300, pref = 0, atl = 0
        assert s["agi"] == pytest.approx(s["gross_ordinary_income"] + s["ss_taxable"])


# ── 4. inputs_summary correctness ────────────────────────────────────────

class TestInputsSummary:
    def setup_method(self):
        # pension=40000, 2026 single, std_ded=16100
        # taxable_ord = max(0, 40000 - 16100) = 23900
        # agi = 40000 (no SS, no pref, no adjustments)
        self.body = client.post("/api/tax", json=_BASE).json()
        self.s = self.body["inputs_summary"]

    def test_gross_ordinary_income(self):
        assert self.s["gross_ordinary_income"] == pytest.approx(40000.0)

    def test_ss_taxable_zero(self):
        assert self.s["ss_taxable"] == pytest.approx(0.0)

    def test_agi(self):
        assert self.s["agi"] == pytest.approx(40000.0)

    def test_standard_deduction(self):
        assert self.s["standard_deduction"] == pytest.approx(16100.0)

    def test_taxable_ordinary(self):
        assert self.s["taxable_ordinary"] == pytest.approx(23900.0)

    def test_taxable_preferential_zero(self):
        assert self.s["taxable_preferential"] == pytest.approx(0.0)


# ── 5. bracket_breakdown correctness ─────────────────────────────────────

class TestBracketBreakdown:
    def setup_method(self):
        # pension=40000, 2026 single, taxable_ord=23900
        # 10% bracket: 0-12400, income=12400, tax=1240
        # 12% bracket: 12400-50400, income=11500, tax=1380
        self.body = client.post("/api/tax", json=_BASE).json()
        self.rows = self.body["federal"]["bracket_breakdown"]

    def test_two_brackets(self):
        assert len(self.rows) == 2

    def test_first_bracket_rate(self):
        assert self.rows[0]["rate"] == pytest.approx(0.10)

    def test_first_bracket_income_taxed(self):
        assert self.rows[0]["income_taxed"] == pytest.approx(12400.0)

    def test_first_bracket_tax_amount(self):
        assert self.rows[0]["tax_amount"] == pytest.approx(1240.0)

    def test_second_bracket_rate(self):
        assert self.rows[1]["rate"] == pytest.approx(0.12)

    def test_second_bracket_income_taxed(self):
        assert self.rows[1]["income_taxed"] == pytest.approx(11500.0)

    def test_second_bracket_tax_amount(self):
        assert self.rows[1]["tax_amount"] == pytest.approx(1380.0)

    def test_total_tax_matches_sum(self):
        total = sum(r["tax_amount"] for r in self.rows)
        assert total == pytest.approx(self.body["federal"]["ordinary_income_tax"])


# ── 6. preferential_breakdown straddles 0%/15% boundary ─────────────────

class TestPrefBreakdown:
    def setup_method(self):
        # 2026 single, pension=20000, qualified_dividends+fixed_ltcg=55000
        # taxable_ord = max(0, 20000 - 16100) = 3900
        # 0% bracket: 0-49450; stack_base=3900; available=45550; income=45550; tax=0
        # 15% bracket: 49450-545500; available=496050; income=9450; tax=9450*0.15=1417.50 → 1418
        payload = {
            "pension": 20000.0,
            "qualified_dividends": 30000.0,
            "fixed_ltcg": 25000.0,
            "filing_status": "single",
            "tax_year": 2026,
        }
        self.body = client.post("/api/tax", json=payload).json()
        self.rows = self.body["federal"]["preferential_breakdown"]

    def test_two_pref_brackets(self):
        assert len(self.rows) == 2

    def test_first_bracket_zero_rate(self):
        assert self.rows[0]["rate"] == pytest.approx(0.0)

    def test_first_bracket_income_in_0pct(self):
        assert self.rows[0]["income_taxed"] == pytest.approx(45550.0)

    def test_first_bracket_no_tax(self):
        assert self.rows[0]["tax_amount"] == pytest.approx(0.0)

    def test_second_bracket_15pct(self):
        assert self.rows[1]["rate"] == pytest.approx(0.15)

    def test_second_bracket_income(self):
        assert self.rows[1]["income_taxed"] == pytest.approx(9450.0)

    def test_second_bracket_tax(self):
        assert self.rows[1]["tax_amount"] == pytest.approx(1418.0)


# ── 7. Missing filing_status → 422 ───────────────────────────────────────

def test_missing_filing_status_returns_422():
    payload = {"pension": 40000.0, "tax_year": 2026}
    resp = client.post("/api/tax", json=payload)
    assert resp.status_code == 422


# ── 8. Unsupported tax year → 422 ────────────────────────────────────────

def test_unsupported_tax_year_returns_422():
    payload = {"pension": 40000.0, "filing_status": "single", "tax_year": 2099}
    resp = client.post("/api/tax", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert "2099" in body["detail"]


# ── 9. include_ohio=false → ohio.included=false only ─────────────────────

def test_ohio_excluded_has_only_included_field():
    payload = {**_BASE, "include_ohio": False}
    body = client.post("/api/tax", json=payload).json()
    ohio = body["ohio"]
    assert ohio["included"] is False
    # All other ohio fields should be absent or null
    for key in ("ohio_agi", "personal_exemption", "ohio_tax"):
        assert ohio.get(key) is None, f"ohio.{key} should be None when excluded"


# ── 10. All income zero → zero tax ───────────────────────────────────────

def test_all_income_zero_returns_zero_tax():
    payload = {"filing_status": "single", "tax_year": 2026}
    body = client.post("/api/tax", json=payload).json()
    assert body["federal"]["total_tax"] == pytest.approx(0.0)
    assert body["summary"]["total_tax"] == pytest.approx(0.0)
    assert body["inputs_summary"]["taxable_ordinary"] == pytest.approx(0.0)
    # bracket_breakdown always has at least one row even with zero income
    assert len(body["federal"]["bracket_breakdown"]) >= 1
    assert body["federal"]["bracket_breakdown"][0]["income_taxed"] == pytest.approx(0.0)


# ── 11. Unexpected exception → 500 ───────────────────────────────────────

def test_unexpected_error_returns_500():
    with patch("api.routers.tax.calculate_federal_tax", side_effect=RuntimeError("boom")):
        resp = client.post("/api/tax", json=_BASE)
    assert resp.status_code == 500
    assert "unexpected" in resp.json()["detail"].lower()
