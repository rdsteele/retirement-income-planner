"""Build the API response fixtures used by the JavaScript page-boot tests.

The fixtures are real responses from the FastAPI app (via TestClient), so the page
scripts are exercised against the actual response shapes. A pytest check
(tests/functional/test_js_fixtures_current.py) fails when the API output no longer
matches the saved files; regenerate them with:

    python3 tests/js/fixtures.py
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from api.main import app  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

_INCOME = {
    "pension": 30000.0,
    "interest": 400.0,
    "ordinary_dividends": 1200.0,
    "qualified_dividends": 800.0,
    "ira_distributions": 5000.0,
    "ss_benefit": 0.0,
    "fixed_ltcg": 3000.0,
}


# A scenario as the planning pages store it, with planned and executed withdrawals.
SAMPLE_SCENARIO = {
    "name": "Sample",
    "saved_at": "2026-01-01T00:00:00",
    "version": "1.0",
    "inputs": {**_INCOME, "pension_taxable": 30000.0, "wages": 2000.0},
    "income_planning": {
        "trad_withdrawals": [{"id": "t", "amount": 5000.0}],
        "withdrawals": [{"id": "h", "amount": 9000.0, "basis": 4000.0}],
        "executed_withdrawals": [
            {"type": "tax_deferred", "amount": 3000.0, "basis": 0.0},
            {"type": "stcg", "amount": 7000.0, "basis": 2500.0},
            {"type": "ltcg", "amount": 6000.0, "basis": 4000.0},
        ],
    },
}


def _context(client: TestClient) -> dict:
    """Return filing_status and tax_year as the API itself offers them."""
    config = client.get("/api/config").json()
    years = client.get("/api/tax-years").json()
    return {
        "filing_status": config["filing_statuses"][0]["value"],
        "tax_year": years["default_year"],
    }


def build_fixtures() -> dict[str, object]:
    client = TestClient(app)
    ctx = _context(client)
    sweep = {"sweep_floor": 0.0, "sweep_ceiling": 20000.0, "sweep_step": 5000.0}
    plan = {
        **_INCOME,
        **ctx,
        **sweep,
        "pension_taxable": 30000.0,
        "essential_spending": 40000.0,
        "discretionary_spending": 5000.0,
        "include_aca": True,
        "include_ohio": True,
        "planned_withdrawals": [{"account_type": "traditional", "amount": 5000.0}],
        "executed_withdrawals": [
            {"withdrawal_type": "stcg", "amount": 7000.0, "basis": 2500.0},
        ],
    }
    return {
        "config": client.get("/api/config").json(),
        "tax_years": client.get("/api/tax-years").json(),
        "tax": client.post("/api/tax", json={**_INCOME, **ctx, "include_ohio": True}).json(),
        "total_cost": client.post(
            "/api/total-cost", json={**_INCOME, **ctx, **sweep, "sweep_mode": "ordinary"}
        ).json(),
        "income_plan_summary": client.post("/api/income-plan/summary", json=plan).json(),
        "income_plan_calculate": client.post("/api/income-plan/calculate", json=plan).json(),
        "scenario_sweep_inputs": _scenario_sweep_inputs(client),
    }


def _scenario_sweep_inputs(client: TestClient) -> dict:
    """The real endpoint's response for SAMPLE_SCENARIO (storage is never touched)."""
    with patch("services.scenarios.load_scenario", return_value=SAMPLE_SCENARIO):
        return client.get("/api/scenarios/Sample/sweep-inputs").json()


def main() -> None:
    FIXTURE_DIR.mkdir(exist_ok=True)
    for name, body in build_fixtures().items():
        (FIXTURE_DIR / f"{name}.json").write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
        print("wrote", name)


if __name__ == "__main__":
    main()
