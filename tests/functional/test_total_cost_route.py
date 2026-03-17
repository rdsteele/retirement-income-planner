"""Functional tests for POST /api/total-cost.

Uses FastAPI TestClient with real bracket data — no mocks.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# ── Shared request builders ──────────────────────────────────────────────

_BASE = {
    "pension": 0.0,
    "interest": 0.0,
    "ordinary_dividends": 0.0,
    "ira_distributions": 0.0,
    "ss_benefit": 0.0,
    "qualified_dividends": 0.0,
    "fixed_ltcg": 0.0,
    "tax_exempt_interest": 0.0,
    "above_the_line_adjustments": 0.0,
    "additional_deductions": 0.0,
    "sweep_mode": "ordinary",
    "filing_status": "single",
    "tax_year": 2026,
    "sweep_floor": 0.0,
    "sweep_ceiling": 5000.0,
    "sweep_step": 1000.0,
    "include_ohio": False,
    "include_aca": False,
}

_BASE_ACA = {
    **_BASE,
    "pension": 30000.0,
    "sweep_ceiling": 40000.0,
    "sweep_step": 1000.0,
    "include_aca": True,
    "aptc_monthly": 500.0,
}


# ── Test 1: Happy path — include_aca=False ───────────────────────────────

class TestHappyPathNoACA:
    def setup_method(self):
        self.resp = client.post("/api/total-cost", json=_BASE)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_top_level_fields(self):
        body = self.body
        assert body["sweep_mode"] == "ordinary"
        assert body["filing_status"] == "single"
        assert body["tax_year"] == 2026
        assert isinstance(body["irmaa_thresholds"], list)
        assert "points" in body
        assert "planning_signals" in body
        assert body["aca_cliff_magi"] == 0.0
        assert body["aptc_annual_max"] == 0.0
        assert body["cliff_sweep_value"] == 0.0

    def test_all_arrays_same_length(self):
        pts = self.body["points"]
        n = len(pts["income"])
        assert n > 0
        assert len(pts["total_tax"]) == n
        assert len(pts["emr"]) == n
        assert len(pts["ss_taxable"]) == n
        assert len(pts["ss_inclusion_rate"]) == n
        assert len(pts["taxable_ordinary"]) == n
        assert len(pts["ohio_tax"]) == n
        assert len(pts["aca_magi"]) == n
        assert len(pts["aptc_annual"]) == n
        assert len(pts["aca_subsidy_loss"]) == n
        assert len(pts["emr_aca"]) == n
        assert len(pts["total_cost_emr"]) == n

    def test_aca_arrays_all_zero_when_no_aca(self):
        pts = self.body["points"]
        assert all(v == 0.0 for v in pts["aca_subsidy_loss"])
        assert all(v == 0.0 for v in pts["emr_aca"])

    def test_components_have_aca_field(self):
        comps = self.body["points"]["components"]
        assert "aca" in comps
        assert all(v == 0.0 for v in comps["aca"])

    def test_planning_signals_fields_present(self):
        signals = self.body["planning_signals"]
        assert "zero_ordinary_space" in signals
        assert "zero_rate_threshold" in signals
        assert "aca_cliff_sweep_value" in signals
        assert "bracket_boundaries" in signals
        assert "ltcg_0pct_remaining" in signals
        assert "torpedo_active" in signals
        assert "ss_fully_taxable" in signals
        assert "distance_to_22pct" in signals
        assert "distance_to_24pct" in signals

    def test_aca_cliff_sweep_value_null_when_no_aca(self):
        assert self.body["planning_signals"]["aca_cliff_sweep_value"] is None


# ── Test 2: Happy path — include_aca=True ────────────────────────────────

class TestHappyPathWithACA:
    def setup_method(self):
        self.resp = client.post("/api/total-cost", json=_BASE_ACA)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_aca_cliff_magi_populated(self):
        # 2026 single ACA cliff = 62600
        assert self.body["aca_cliff_magi"] == pytest.approx(62600.0)

    def test_aptc_annual_max_populated(self):
        # _BASE_ACA: pension=30000, no adjustments, sweep_floor=0
        # floor MAGI = 30000; schedule at 30000: monthly=883 → annual=10596
        assert self.body["aptc_annual_max"] == pytest.approx(10596.0)

    def test_cliff_sweep_value_populated(self):
        # pension=30000, cliff_magi=62600 → cliff_sweep=32600
        assert self.body["cliff_sweep_value"] == pytest.approx(32600.0)

    def test_aca_subsidy_loss_nonzero_at_cliff(self):
        pts = self.body["points"]
        # Some points past the cliff should have aca_subsidy_loss > 0
        assert any(v > 0 for v in pts["aca_subsidy_loss"])

    def test_emr_aca_spike_at_cliff(self):
        # emr_aca is non-zero only at the cliff point
        pts = self.body["points"]
        assert any(v > 0 for v in pts["emr_aca"])

    def test_aca_cliff_sweep_value_signal_set(self):
        signal = self.body["planning_signals"]["aca_cliff_sweep_value"]
        assert signal is not None
        assert signal == pytest.approx(32600.0)


# ── Test 3: aca_cliff_sweep_value matches cliff in points ────────────────

class TestACACliffConsistency:
    def setup_method(self):
        self.resp = client.post("/api/total-cost", json=_BASE_ACA)
        self.body = self.resp.json()

    def test_aca_cliff_sweep_value_matches_result_cliff(self):
        # Planning signal uses result.cliff_sweep_value (exact formula)
        signal = self.body["planning_signals"]["aca_cliff_sweep_value"]
        top_level = self.body["cliff_sweep_value"]
        assert signal == pytest.approx(top_level)

    def test_aca_subsidy_loss_zero_at_sweep_floor(self):
        # Subsidy loss is zero at the sweep floor (that is the baseline MAGI).
        pts = self.body["points"]
        assert pts["aca_subsidy_loss"][0] == 0.0


# ── Test 4: bracket_boundaries identifies rate transitions ───────────────

class TestBracketBoundaries:
    def setup_method(self):
        req = {**_BASE, "sweep_ceiling": 60000.0, "sweep_step": 1000.0}
        self.resp = client.post("/api/total-cost", json=req)
        self.body = self.resp.json()

    def test_status_200(self):
        assert self.resp.status_code == 200

    def test_at_least_three_boundaries(self):
        # 0%, 10%, 12% boundaries visible in 0-60k range
        bounds = self.body["planning_signals"]["bracket_boundaries"]
        assert len(bounds) >= 3

    def test_first_boundary_is_zero_rate(self):
        bounds = self.body["planning_signals"]["bracket_boundaries"]
        assert bounds[0]["rate"] == 0.0
        assert bounds[0]["sweep_value"] == 0.0
        assert "0%" in bounds[0]["notes"]

    def test_second_boundary_is_ten_percent(self):
        bounds = self.body["planning_signals"]["bracket_boundaries"]
        # 10% bracket starts after standard deduction (2026: 16100)
        ten = next(b for b in bounds if b["rate"] == pytest.approx(0.10))
        assert ten["sweep_value"] > 0.0
        assert "10%" in ten["notes"]

    def test_boundaries_monotonically_increasing(self):
        bounds = self.body["planning_signals"]["bracket_boundaries"]
        values = [b["sweep_value"] for b in bounds]
        assert values == sorted(values)

    def test_boundaries_have_required_keys(self):
        bounds = self.body["planning_signals"]["bracket_boundaries"]
        for b in bounds:
            assert "sweep_value" in b
            assert "rate" in b
            assert "notes" in b


# ── Test 5: zero_rate_threshold ──────────────────────────────────────────

class TestZeroRateThreshold:
    def setup_method(self):
        req = {**_BASE, "sweep_ceiling": 30000.0, "sweep_step": 1000.0}
        self.resp = client.post("/api/total-cost", json=req)
        self.body = self.resp.json()

    def test_zero_rate_threshold_is_first_ordinary_income_point(self):
        # 2026 single std_ded=16100; with step=1000, first emr_ordinary > 0 at 16000
        threshold = self.body["planning_signals"]["zero_rate_threshold"]
        assert threshold == pytest.approx(16000.0)

    def test_threshold_is_in_income_array(self):
        threshold = self.body["planning_signals"]["zero_rate_threshold"]
        incomes = self.body["points"]["income"]
        assert threshold in incomes

    def test_emr_ordinary_zero_below_threshold(self):
        threshold = self.body["planning_signals"]["zero_rate_threshold"]
        pts = self.body["points"]
        for income, rate in zip(pts["income"], pts["components"]["ordinary"]):
            if income < threshold:
                assert rate == 0.0


# ── Test 6: zero_ordinary_space ──────────────────────────────────────────

class TestZeroOrdinarySpace:
    def test_no_fixed_income(self):
        req = {**_BASE, "sweep_ceiling": 5000.0}
        resp = client.post("/api/total-cost", json=req)
        space = resp.json()["planning_signals"]["zero_ordinary_space"]
        # std_ded=16100, fixed_ordinary=0, ss_taxable=0 → 16100
        assert space == pytest.approx(16100.0)

    def test_with_pension(self):
        req = {**_BASE, "pension": 10000.0, "sweep_ceiling": 5000.0}
        resp = client.post("/api/total-cost", json=req)
        space = resp.json()["planning_signals"]["zero_ordinary_space"]
        # std_ded=16100 - pension=10000 = 6100
        assert space == pytest.approx(6100.0)

    def test_pension_exceeds_standard_deduction(self):
        req = {**_BASE, "pension": 20000.0, "sweep_ceiling": 5000.0}
        resp = client.post("/api/total-cost", json=req)
        space = resp.json()["planning_signals"]["zero_ordinary_space"]
        # 16100 - 20000 < 0 → clamped to 0
        assert space == pytest.approx(0.0)

    def test_additional_deductions_expand_space(self):
        req = {**_BASE, "pension": 10000.0, "additional_deductions": 5000.0}
        resp = client.post("/api/total-cost", json=req)
        space = resp.json()["planning_signals"]["zero_ordinary_space"]
        # 16100 + 5000 - 10000 = 11100
        assert space == pytest.approx(11100.0)


# ── Test 7: Missing required field returns 422 ───────────────────────────

class TestMissingRequiredField:
    def test_missing_sweep_mode(self):
        req = {k: v for k, v in _BASE.items() if k != "sweep_mode"}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422

    def test_missing_filing_status(self):
        req = {k: v for k, v in _BASE.items() if k != "filing_status"}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422

    def test_missing_tax_year(self):
        req = {k: v for k, v in _BASE.items() if k != "tax_year"}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422


# ── Test 8: Invalid sweep_mode returns 422 ───────────────────────────────

class TestInvalidSweepMode:
    def test_bad_sweep_mode(self):
        req = {**_BASE, "sweep_mode": "capital_gains"}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422

    def test_error_message_mentions_sweep_mode(self):
        req = {**_BASE, "sweep_mode": "bogus"}
        resp = client.post("/api/total-cost", json=req)
        assert "sweep_mode" in resp.json()["detail"].lower()


# ── Test 9: Unsupported tax_year returns 422 ─────────────────────────────

class TestUnsupportedTaxYear:
    def test_unsupported_year(self):
        req = {**_BASE, "tax_year": 2019}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422

    def test_error_message_mentions_year(self):
        req = {**_BASE, "tax_year": 2019}
        resp = client.post("/api/total-cost", json=req)
        assert "2019" in resp.json()["detail"]


# ── Test 10: Negative monetary field returns 422 ─────────────────────────

class TestNegativeMonetaryField:
    def test_negative_pension(self):
        req = {**_BASE, "pension": -1.0}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422

    def test_negative_aptc_monthly(self):
        req = {**_BASE, "aptc_monthly": -100.0}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422

    def test_negative_sweep_step(self):
        req = {**_BASE, "sweep_step": -100.0}
        resp = client.post("/api/total-cost", json=req)
        assert resp.status_code == 422
