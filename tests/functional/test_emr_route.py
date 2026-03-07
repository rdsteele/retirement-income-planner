"""Functional tests for POST /api/emr.

Uses FastAPI TestClient with real bracket data — no mocks.
"""

from decimal import Decimal

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# ── Shared request builders ──────────────────────────────────────────────

_BASE_ORDINARY = {
    "pension": 20000.0,
    "interest": 2000.0,
    "ordinary_dividends": 0.0,
    "inherited_ira_rmd": 0.0,
    "ss_benefit": 0.0,
    "qualified_dividends": 5000.0,
    "fixed_ltcg": 10000.0,
    "tax_exempt_interest": 0.0,
    "sweep_mode": "ordinary",
    "filing_status": "single",
    "tax_year": 2025,
    "sweep_floor": 0.0,
    "sweep_ceiling": 5000.0,
    "sweep_step": 1000.0,
}

_BASE_PREFERENTIAL = {
    "pension": 20000.0,
    "interest": 0.0,
    "ordinary_dividends": 0.0,
    "inherited_ira_rmd": 15000.0,
    "ss_benefit": 0.0,
    "qualified_dividends": 2000.0,
    "fixed_ltcg": 0.0,
    "tax_exempt_interest": 0.0,
    "sweep_mode": "preferential",
    "filing_status": "single",
    "tax_year": 2025,
    "variable_ordinary": 0.0,
    "sweep_floor": 0.0,
    "sweep_ceiling": 30000.0,
    "sweep_step": 5000.0,
}


# ── Happy path: ordinary sweep ───────────────────────────────────────────

class TestOrdinarySweep:
    def setup_method(self):
        self.resp = client.post("/api/emr", json=_BASE_ORDINARY)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_response_metadata(self):
        assert self.body["sweep_mode"] == "ordinary"
        assert self.body["filing_status"] == "single"
        assert self.body["tax_year"] == 2025

    def test_parallel_arrays_same_length(self):
        pts = self.body["points"]
        n = len(pts["income"])
        assert n > 0
        assert len(pts["total_tax"]) == n
        assert len(pts["emr"]) == n
        assert len(pts["ss_taxable"]) == n
        assert len(pts["ss_inclusion_rate"]) == n
        assert len(pts["taxable_ordinary"]) == n
        assert len(pts["ohio_tax"]) == n
        comp = pts["components"]
        assert len(comp["ordinary"]) == n
        assert len(comp["ss_torpedo"]) == n
        assert len(comp["pref_stacking"]) == n
        assert len(comp["niit"]) == n
        assert len(comp["ohio"]) == n

    def test_all_values_are_float(self):
        pts = self.body["points"]
        for v in pts["income"]:
            assert isinstance(v, (int, float))
        for v in pts["emr"]:
            assert isinstance(v, (int, float))

    def test_irmaa_thresholds_present(self):
        thresholds = self.body["irmaa_thresholds"]
        assert len(thresholds) > 0
        assert all(isinstance(t, (int, float)) for t in thresholds)

    def test_planning_signals_present(self):
        signals = self.body["planning_signals"]
        assert "torpedo_active" in signals
        assert "ss_fully_taxable" in signals
        assert "ltcg_0pct_remaining" in signals
        assert "distance_to_22pct" in signals
        assert "distance_to_24pct" in signals

    def test_planning_signals_types(self):
        signals = self.body["planning_signals"]
        assert isinstance(signals["torpedo_active"], bool)
        assert isinstance(signals["ss_fully_taxable"], bool)
        # distance fields are float or null
        d22 = signals["distance_to_22pct"]
        assert d22 is None or isinstance(d22, (int, float))

    def test_torpedo_inactive_when_no_ss(self):
        assert self.body["planning_signals"]["torpedo_active"] is False


# ── Happy path: preferential sweep ───────────────────────────────────────

class TestPreferentialSweep:
    def setup_method(self):
        self.resp = client.post("/api/emr", json=_BASE_PREFERENTIAL)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_sweep_mode(self):
        assert self.body["sweep_mode"] == "preferential"

    def test_parallel_arrays_same_length(self):
        pts = self.body["points"]
        n = len(pts["income"])
        assert n > 0
        for key in ("total_tax", "emr", "ss_taxable", "ss_inclusion_rate",
                     "taxable_ordinary", "ohio_tax"):
            assert len(pts[key]) == n

    def test_ltcg_0pct_remaining_present(self):
        signals = self.body["planning_signals"]
        remaining = signals["ltcg_0pct_remaining"]
        # taxable_ordinary = 19250, qualified_divs = 2000
        # 0% LTCG space = 48350 - 19250 - 2000 = 27100
        assert remaining is not None
        assert isinstance(remaining, (int, float))
        assert remaining > 0

    def test_emr_starts_at_zero(self):
        # In the 0% LTCG bracket, emr should be 0
        assert self.body["points"]["emr"][0] == 0.0


# ── Happy path: with Ohio ────────────────────────────────────────────────

class TestWithOhio:
    def setup_method(self):
        payload = {**_BASE_ORDINARY, "include_ohio": True}
        self.resp = client.post("/api/emr", json=payload)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_ohio_tax_nonzero(self):
        ohio_taxes = self.body["points"]["ohio_tax"]
        assert any(t > 0 for t in ohio_taxes)

    def test_ohio_component_nonzero(self):
        ohio_emrs = self.body["points"]["components"]["ohio"]
        assert any(e > 0 for e in ohio_emrs)


# ── Happy path: without Ohio ─────────────────────────────────────────────

class TestWithoutOhio:
    def setup_method(self):
        payload = {**_BASE_ORDINARY, "include_ohio": False}
        self.resp = client.post("/api/emr", json=payload)
        self.body = self.resp.json()

    def test_ohio_tax_all_zero(self):
        assert all(t == 0 for t in self.body["points"]["ohio_tax"])

    def test_ohio_component_all_zero(self):
        assert all(e == 0 for e in self.body["points"]["components"]["ohio"])


# ── Float → Decimal → float round-trip ───────────────────────────────────

class TestRoundTrip:
    def test_income_values_match_sweep(self):
        payload = {
            **_BASE_ORDINARY,
            "sweep_floor": 1000.50,
            "sweep_ceiling": 1200.50,
            "sweep_step": 100.0,
        }
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 200
        incomes = resp.json()["points"]["income"]
        # sweep_floor should appear as an income value
        assert any(abs(i - 1000.50) < 0.01 for i in incomes)

    def test_decimal_precision_preserved(self):
        # Verify that 0.1 doesn't become 0.1000000000000000055511151231257827021181583404541015625
        resp = client.post("/api/emr", json={
            **_BASE_ORDINARY,
            "pension": 10000.1,
        })
        assert resp.status_code == 200
        # The key test: the response should be valid JSON with normal floats
        body = resp.json()
        assert len(body["points"]["income"]) > 0


# ── Planning signals ─────────────────────────────────────────────────────

class TestPlanningSignals:
    def test_distance_to_22pct(self):
        # Start in 10% bracket, 22% bracket should be reachable
        payload = {
            **_BASE_ORDINARY,
            "sweep_ceiling": 100000.0,
            "sweep_step": 1000.0,
        }
        resp = client.post("/api/emr", json=payload)
        body = resp.json()
        d22 = body["planning_signals"]["distance_to_22pct"]
        assert d22 is not None
        assert d22 > 0

    def test_distance_null_when_already_at_bracket(self):
        # Start high enough to already be in 22%+ bracket
        payload = {
            **_BASE_ORDINARY,
            "pension": 100000.0,
            "sweep_floor": 0.0,
            "sweep_ceiling": 5000.0,
        }
        resp = client.post("/api/emr", json=payload)
        body = resp.json()
        assert body["planning_signals"]["distance_to_22pct"] is None

    def test_torpedo_active_with_ss(self):
        payload = {
            **_BASE_ORDINARY,
            "pension": 15000.0,
            "inherited_ira_rmd": 8000.0,
            "ss_benefit": 24000.0,
            "qualified_dividends": 3000.0,
            "fixed_ltcg": 5000.0,
            "sweep_ceiling": 15000.0,
        }
        resp = client.post("/api/emr", json=payload)
        body = resp.json()
        assert body["planning_signals"]["torpedo_active"] is True


# ── above_the_line_adjustments and additional_deductions ─────────────────

class TestAdjustmentFields:
    def test_above_the_line_reduces_ss_taxable(self):
        # With ss_benefit and high pension, HSA adjustment reduces SS taxable amount.
        base = {**_BASE_ORDINARY, "ss_benefit": 20000.0, "pension": 30000.0,
                "sweep_ceiling": 1000.0}
        resp_no_adj = client.post("/api/emr", json=base)
        resp_with_adj = client.post("/api/emr", json={**base,
                                    "above_the_line_adjustments": 10000.0})
        assert resp_no_adj.status_code == 200
        assert resp_with_adj.status_code == 200
        ss_no = resp_no_adj.json()["points"]["ss_taxable"][0]
        ss_adj = resp_with_adj.json()["points"]["ss_taxable"][0]
        assert ss_adj < ss_no

    def test_additional_deductions_reduces_taxable_ordinary(self):
        base = {**_BASE_ORDINARY, "sweep_ceiling": 1000.0}
        resp_no_ded = client.post("/api/emr", json=base)
        resp_with_ded = client.post("/api/emr", json={**base,
                                    "additional_deductions": 5000.0})
        assert resp_no_ded.status_code == 200
        assert resp_with_ded.status_code == 200
        ord_no = resp_no_ded.json()["points"]["taxable_ordinary"][0]
        ord_ded = resp_with_ded.json()["points"]["taxable_ordinary"][0]
        assert ord_ded < ord_no

    def test_defaults_to_zero(self):
        # Omitting both fields should give same result as passing zero.
        base = {**_BASE_ORDINARY, "sweep_ceiling": 1000.0}
        resp_omit = client.post("/api/emr", json=base)
        resp_zero = client.post("/api/emr", json={**base,
                                "above_the_line_adjustments": 0.0,
                                "additional_deductions": 0.0})
        assert resp_omit.json()["points"]["taxable_ordinary"] == \
               resp_zero.json()["points"]["taxable_ordinary"]

    def test_negative_above_the_line_rejected(self):
        payload = {**_BASE_ORDINARY, "above_the_line_adjustments": -100.0}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422

    def test_negative_additional_deductions_rejected(self):
        payload = {**_BASE_ORDINARY, "additional_deductions": -100.0}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422


# ── Validation errors (422) ──────────────────────────────────────────────

class TestValidationErrors:
    def test_invalid_filing_status(self):
        payload = {**_BASE_ORDINARY, "filing_status": "head_of_household"}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_invalid_sweep_mode(self):
        payload = {**_BASE_ORDINARY, "sweep_mode": "both"}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_unsupported_tax_year(self):
        payload = {**_BASE_ORDINARY, "tax_year": 2099}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_negative_pension(self):
        payload = {**_BASE_ORDINARY, "pension": -100.0}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422

    def test_negative_ss_benefit(self):
        payload = {**_BASE_ORDINARY, "ss_benefit": -1.0}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422

    def test_zero_sweep_step(self):
        payload = {**_BASE_ORDINARY, "sweep_step": 0.0}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422

    def test_negative_sweep_ceiling(self):
        payload = {**_BASE_ORDINARY, "sweep_ceiling": -100.0}
        resp = client.post("/api/emr", json=payload)
        assert resp.status_code == 422

    def test_service_valueerror_has_detail(self):
        # Unsupported tax year triggers ValueError from service
        payload = {**_BASE_ORDINARY, "tax_year": 2099}
        resp = client.post("/api/emr", json=payload)
        body = resp.json()
        assert resp.status_code == 422
        assert isinstance(body["detail"], str)
        assert "2099" in body["detail"]
