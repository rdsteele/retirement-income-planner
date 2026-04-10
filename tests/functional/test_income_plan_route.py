"""Functional tests for POST /api/income-plan/summary and /api/income-plan/calculate.

Uses FastAPI TestClient with real bracket data — no mocks.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# ── Shared base request ───────────────────────────────────────────────────

_BASE = {
    "filing_status": "single",
    "tax_year": 2026,
    "pension": 0.0,
    "pension_taxable": 0.0,
    "interest": 0.0,
    "ordinary_dividends": 0.0,
    "ira_distributions": 0.0,
    "ss_benefit": 0.0,
    "qualified_dividends": 0.0,
    "fixed_ltcg": 0.0,
    "tax_exempt_interest": 0.0,
    "above_the_line_adjustments": 0.0,
    "essential_spending": 0.0,
    "discretionary_spending": 0.0,
    "include_aca": False,
    "aca_cliff_magi": 0.0,
    "estimated_taxes": 0.0,
    "planned_withdrawals": [],
    "executed_withdrawals": [],
    # calculate-only fields (ignored by summary endpoint)
    "sweep_floor": 0.0,
    "sweep_ceiling": 5000.0,
    "sweep_step": 1000.0,
    "include_ohio": False,
}


# ── /api/income-plan/summary ──────────────────────────────────────────────

class TestSummaryHappyPath:
    def setup_method(self):
        self.resp = client.post("/api/income-plan/summary", json=_BASE)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_all_fields_present(self):
        required = {
            "magi", "forced_ordinary", "forced_preferential",
            "withdrawal_ordinary", "withdrawal_preferential",
            "executed_ordinary", "executed_preferential",
            "ss_taxable", "provisional_income",
            "total_spending", "total_income", "shortfall",
            "aca_distance", "aca_cliff_magi",
            "total_taxable_withdrawals", "total_traditional_withdrawals",
            "total_roth_withdrawals", "total_hsa_withdrawals",
            "total_pension_annuity", "total_ss_benefit",
            "total_all_withdrawals",
        }
        assert required.issubset(self.body.keys())

    def test_zero_income_yields_zero_magi(self):
        assert self.body["magi"] == 0.0

    def test_no_spending_shortfall_is_null(self):
        assert self.body["shortfall"] is None

    def test_no_aca_distance_when_cliff_zero(self):
        assert self.body["aca_distance"] is None


class TestSummaryWithPension:
    def setup_method(self):
        body = {**_BASE, "pension": 30000.0, "pension_taxable": 30000.0}
        self.resp = client.post("/api/income-plan/summary", json=body)
        self.body = self.resp.json()

    def test_magi_equals_pension_taxable(self):
        assert self.body["magi"] == 30000.0

    def test_forced_ordinary_equals_pension_taxable(self):
        assert self.body["forced_ordinary"] == 30000.0

    def test_forced_preferential_is_zero(self):
        assert self.body["forced_preferential"] == 0.0

    def test_pension_annuity_shows_gross(self):
        assert self.body["total_pension_annuity"] == 30000.0


class TestSummarySSAccuracy:
    """Verify SS taxability uses real service, not single-filer JS approximation."""

    def test_single_ss_below_threshold_zero_taxable(self):
        # PI = 15000 + 10000 = 25000 → exactly at threshold → 0 taxable
        body = {**_BASE, "ss_benefit": 20000.0, "pension": 15000.0, "pension_taxable": 15000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["ss_taxable"] == 0.0

    def test_mfj_uses_higher_thresholds(self):
        # MFJ tier_1 = 32000; PI = 20000 + 12000 = 32000 → no taxable SS
        body = {**_BASE, "filing_status": "mfj", "ss_benefit": 24000.0, "pension": 20000.0, "pension_taxable": 20000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ss_taxable"] == 0.0
        assert data["provisional_income"] == 32000.0


class TestSummaryWithdrawals:
    def test_planned_traditional_increases_magi(self):
        body = {
            **_BASE,
            "planned_withdrawals": [
                {"account_type": "traditional", "amount": 20000.0, "basis": 0.0}
            ],
        }
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["magi"] == 20000.0

    def test_planned_roth_does_not_affect_magi(self):
        body = {
            **_BASE,
            "planned_withdrawals": [
                {"account_type": "roth", "amount": 15000.0, "basis": 0.0}
            ],
        }
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["magi"] == 0.0
        assert resp.json()["total_roth_withdrawals"] == 15000.0

    def test_executed_ltcg_adds_preferential_income(self):
        body = {
            **_BASE,
            "executed_withdrawals": [
                {"withdrawal_type": "ltcg", "amount": 10000.0, "basis": 7000.0}
            ],
        }
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["executed_preferential"] == 3000.0


class TestSummaryACADistance:
    def test_distance_computed_correctly(self):
        body = {**_BASE, "pension": 30000.0, "pension_taxable": 30000.0, "aca_cliff_magi": 62600.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["aca_distance"] == pytest.approx(32600.0)

    def test_negative_distance_when_over_cliff(self):
        body = {**_BASE, "pension": 70000.0, "pension_taxable": 70000.0, "aca_cliff_magi": 62600.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["aca_distance"] < 0.0


class TestSummaryShortfall:
    def test_shortfall_positive_when_expenses_exceed_income(self):
        body = {**_BASE, "pension": 20000.0, "pension_taxable": 20000.0, "essential_spending": 30000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["shortfall"] > 0.0

    def test_surplus_when_income_exceeds_expenses(self):
        body = {**_BASE, "pension": 50000.0, "pension_taxable": 50000.0, "essential_spending": 20000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["shortfall"] < 0.0


class TestSummaryPensionGrossTaxableSplit:
    """Verify gross pension flows to withdrawals, taxable to MAGI."""

    def test_magi_uses_taxable(self):
        body = {**_BASE, "pension": 10000.0, "pension_taxable": 7000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 200
        assert resp.json()["magi"] == 7000.0

    def test_forced_ordinary_uses_taxable(self):
        body = {**_BASE, "pension": 10000.0, "pension_taxable": 7000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.json()["forced_ordinary"] == 7000.0

    def test_pension_annuity_shows_gross(self):
        body = {**_BASE, "pension": 10000.0, "pension_taxable": 7000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.json()["total_pension_annuity"] == 10000.0

    def test_shortfall_uses_gross(self):
        body = {**_BASE, "pension": 10000.0, "pension_taxable": 7000.0, "essential_spending": 12000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.json()["shortfall"] == pytest.approx(2000.0)

    def test_ss_benefit_in_response(self):
        body = {**_BASE, "ss_benefit": 24000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.json()["total_ss_benefit"] == 24000.0

    def test_forced_income_merged_into_withdrawal_totals(self):
        body = {**_BASE, "interest": 3000.0, "ira_distributions": 5000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        data = resp.json()
        assert data["total_taxable_withdrawals"] == 3000.0
        assert data["total_traditional_withdrawals"] == 5000.0


class TestSummaryValidation:
    def test_invalid_filing_status_raises_422(self):
        body = {**_BASE, "filing_status": "mfs", "ss_benefit": 20000.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 422

    def test_negative_amount_raises_422(self):
        body = {**_BASE, "pension": -100.0}
        resp = client.post("/api/income-plan/summary", json=body)
        assert resp.status_code == 422


# ── /api/income-plan/calculate ────────────────────────────────────────────

class TestCalculateHappyPath:
    def setup_method(self):
        self.resp = client.post("/api/income-plan/calculate", json=_BASE)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_top_level_fields_present(self):
        assert "sweep_mode" in self.body
        assert "filing_status" in self.body
        assert "tax_year" in self.body
        assert "points" in self.body
        assert "planning_signals" in self.body
        assert "irmaa_thresholds" in self.body
        assert "aca_cliff_magi" in self.body

    def test_sweep_mode_is_ordinary(self):
        assert self.body["sweep_mode"] == "ordinary"

    def test_filing_status_echoed(self):
        assert self.body["filing_status"] == "single"

    def test_all_point_arrays_same_length(self):
        pts = self.body["points"]
        n = len(pts["income"])
        assert n > 0
        for key in ("total_tax", "emr", "ss_taxable", "taxable_ordinary"):
            assert len(pts[key]) == n, f"array length mismatch for {key}"


class TestCalculateWithdrawalsAugmented:
    """Verify that traditional withdrawals are merged into ira_distributions for the sweep."""

    def test_traditional_withdrawal_affects_sweep_floor_tax(self):
        # With $20k traditional withdrawal at sweep floor, tax should exceed zero-income case
        body_no_trad = {**_BASE, "sweep_ceiling": 1000.0}
        body_with_trad = {
            **_BASE,
            "sweep_ceiling": 1000.0,
            "planned_withdrawals": [
                {"account_type": "traditional", "amount": 20000.0, "basis": 0.0}
            ],
        }
        resp_no = client.post("/api/income-plan/calculate", json=body_no_trad)
        resp_w = client.post("/api/income-plan/calculate", json=body_with_trad)
        assert resp_no.status_code == 200
        assert resp_w.status_code == 200
        tax_no = resp_no.json()["points"]["total_tax"][0]
        tax_w = resp_w.json()["points"]["total_tax"][0]
        assert tax_w > tax_no

    def test_roth_withdrawal_does_not_affect_sweep_floor_tax(self):
        body_no_roth = {**_BASE, "sweep_ceiling": 1000.0}
        body_with_roth = {
            **_BASE,
            "sweep_ceiling": 1000.0,
            "planned_withdrawals": [
                {"account_type": "roth", "amount": 20000.0, "basis": 0.0}
            ],
        }
        resp_no = client.post("/api/income-plan/calculate", json=body_no_roth)
        resp_w = client.post("/api/income-plan/calculate", json=body_with_roth)
        tax_no = resp_no.json()["points"]["total_tax"][0]
        tax_w = resp_w.json()["points"]["total_tax"][0]
        assert tax_no == tax_w


class TestCalculatePlanningSignals:
    def test_planning_signals_fields_present(self):
        resp = client.post("/api/income-plan/calculate", json=_BASE)
        signals = resp.json()["planning_signals"]
        required = {
            "zero_ordinary_space", "zero_rate_threshold",
            "aca_cliff_sweep_value", "bracket_boundaries",
            "ltcg_0pct_remaining", "torpedo_active", "ss_fully_taxable",
            "distance_to_22pct", "distance_to_24pct",
        }
        assert required.issubset(signals.keys())


class TestCalculateValidation:
    def test_negative_pension_raises_422(self):
        body = {**_BASE, "pension": -500.0}
        resp = client.post("/api/income-plan/calculate", json=body)
        assert resp.status_code == 422

    def test_unsupported_filing_status_with_ss_raises_422(self):
        # "mfs" is rejected by the SS taxability service → ValueError → 422
        body = {**_BASE, "filing_status": "mfs", "ss_benefit": 20000.0}
        resp = client.post("/api/income-plan/calculate", json=body)
        assert resp.status_code == 422
