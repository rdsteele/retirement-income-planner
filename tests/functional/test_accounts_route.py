"""Functional tests for the accounts API routes.

Uses FastAPI TestClient. All file I/O is redirected to a tmp_path-isolated
accounts.json — no test touches data/accounts.json.
"""

import pytest
from fastapi.testclient import TestClient

import services.accounts as svc
from api.main import app

client = TestClient(app)


# ── Isolation fixture ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_storage(tmp_path, monkeypatch):
    """Redirect every service function to a fresh temp file per test.

    Lambdas capture the *original* functions before any patching so that
    get_portfolio_summary's internal call to load_accounts(_path) doesn't
    create a double-_path conflict that functools.partial would cause.
    """
    path = tmp_path / "accounts.json"

    _load     = svc.load_accounts
    _get      = svc.get_account
    _create   = svc.create_account
    _update   = svc.update_account
    _delete   = svc.delete_account
    _create_h = svc.create_holding
    _update_h = svc.update_holding
    _delete_h = svc.delete_holding
    _summary  = svc.get_portfolio_summary

    monkeypatch.setattr(svc, "load_accounts",
        lambda _path=path: _load(_path))
    monkeypatch.setattr(svc, "get_account",
        lambda account_id, _path=path: _get(account_id, _path))
    monkeypatch.setattr(svc, "create_account",
        lambda data, _path=path: _create(data, _path))
    monkeypatch.setattr(svc, "update_account",
        lambda account_id, data, _path=path: _update(account_id, data, _path))
    monkeypatch.setattr(svc, "delete_account",
        lambda account_id, _path=path: _delete(account_id, _path))
    monkeypatch.setattr(svc, "create_holding",
        lambda account_id, data, _path=path: _create_h(account_id, data, _path))
    monkeypatch.setattr(svc, "update_holding",
        lambda account_id, holding_id, data, _path=path: _update_h(account_id, holding_id, data, _path))
    monkeypatch.setattr(svc, "delete_holding",
        lambda account_id, holding_id, _path=path: _delete_h(account_id, holding_id, _path))
    monkeypatch.setattr(svc, "get_portfolio_summary",
        lambda _path=path: _summary(_path))


# ── Local helpers ─────────────────────────────────────────────────────────

def _create_account(payload: dict) -> dict:
    resp = client.post("/api/accounts", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _add_holding(account_id: str, ticker: str, basis: float, value: float) -> dict:
    resp = client.post(
        f"/api/accounts/{account_id}/holdings",
        json={"ticker": ticker, "basis": basis, "value": value},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Account CRUD ──────────────────────────────────────────────────────────

def test_list_accounts_empty():
    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_taxable_account():
    resp = client.post("/api/accounts", json={"name": "Brokerage", "account_type": "taxable"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Brokerage"
    assert body["account_type"] == "taxable"
    assert "id" in body and body["id"]
    assert body["holdings"] == []
    assert body["total_value"] == 0.0
    assert body["total_basis"] == 0.0
    assert body["total_unrealized_gain"] == 0.0


def test_create_traditional_account():
    resp = client.post(
        "/api/accounts",
        json={"name": "401k", "account_type": "traditional", "balance": 150000.0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_type"] == "traditional"
    assert body["balance"] == 150000.0
    assert body["holdings"] is None


def test_create_roth_account():
    resp = client.post(
        "/api/accounts",
        json={"name": "Roth IRA", "account_type": "roth", "balance": 80000.0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_type"] == "roth"
    assert body["balance"] == 80000.0


def test_create_hsa_account_with_annual_contribution():
    resp = client.post(
        "/api/accounts",
        json={
            "name": "HSA",
            "account_type": "hsa",
            "balance": 15000.0,
            "annual_contribution": 4150.0,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_type"] == "hsa"
    assert body["balance"] == 15000.0
    assert body["annual_contribution"] == 4150.0


def test_get_account_returns_correct():
    created = _create_account(
        {"name": "My Roth", "account_type": "roth", "balance": 40000.0}
    )
    resp = client.get(f"/api/accounts/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == "My Roth"
    assert body["balance"] == 40000.0


def test_get_account_not_found():
    assert client.get("/api/accounts/nonexistent-id").status_code == 404


def test_update_account_id_preserved():
    created = _create_account(
        {"name": "Old Name", "account_type": "traditional", "balance": 10000.0}
    )
    account_id = created["id"]
    resp = client.put(
        f"/api/accounts/{account_id}",
        json={"name": "New Name", "account_type": "traditional", "balance": 20000.0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == account_id
    assert body["name"] == "New Name"
    assert body["balance"] == 20000.0


def test_update_account_not_found():
    resp = client.put(
        "/api/accounts/nonexistent-id",
        json={"name": "X", "account_type": "traditional"},
    )
    assert resp.status_code == 404


def test_delete_account_returns_204_and_removes():
    created = _create_account(
        {"name": "To Delete", "account_type": "roth", "balance": 5000.0}
    )
    account_id = created["id"]
    assert client.delete(f"/api/accounts/{account_id}").status_code == 204
    assert client.get(f"/api/accounts/{account_id}").status_code == 404
    assert all(a["id"] != account_id for a in client.get("/api/accounts").json())


def test_delete_account_not_found():
    assert client.delete("/api/accounts/nonexistent-id").status_code == 404


# ── Holdings CRUD ─────────────────────────────────────────────────────────

def test_add_holding_returns_201_with_unrealized_gain():
    acc = _create_account({"name": "Brokerage", "account_type": "taxable"})
    resp = client.post(
        f"/api/accounts/{acc['id']}/holdings",
        json={"ticker": "AAPL", "basis": 8000.0, "value": 10000.0},
    )
    assert resp.status_code == 201
    holdings = resp.json()["holdings"]
    assert len(holdings) == 1
    h = holdings[0]
    assert h["ticker"] == "AAPL"
    assert h["basis"] == 8000.0
    assert h["value"] == 10000.0
    assert h["unrealized_gain"] == 2000.0


def test_add_holding_account_not_found():
    resp = client.post(
        "/api/accounts/nonexistent-id/holdings",
        json={"ticker": "SPY", "basis": 1000.0, "value": 1200.0},
    )
    assert resp.status_code == 404


def test_update_holding_returns_updated_account():
    acc = _create_account({"name": "Brokerage", "account_type": "taxable"})
    updated = _add_holding(acc["id"], "MSFT", 5000.0, 6000.0)
    holding_id = updated["holdings"][0]["id"]

    resp = client.put(
        f"/api/accounts/{acc['id']}/holdings/{holding_id}",
        json={"ticker": "MSFT", "basis": 5000.0, "value": 7500.0},
    )
    assert resp.status_code == 200
    h = resp.json()["holdings"][0]
    assert h["value"] == 7500.0
    assert h["unrealized_gain"] == 2500.0


def test_update_holding_not_found():
    acc = _create_account({"name": "Brokerage", "account_type": "taxable"})
    resp = client.put(
        f"/api/accounts/{acc['id']}/holdings/nonexistent-hid",
        json={"ticker": "X", "basis": 100.0, "value": 200.0},
    )
    assert resp.status_code == 404


def test_delete_holding_removes_and_returns_updated_account():
    acc = _create_account({"name": "Brokerage", "account_type": "taxable"})
    updated = _add_holding(acc["id"], "VTI", 10000.0, 12000.0)
    holding_id = updated["holdings"][0]["id"]

    resp = client.delete(f"/api/accounts/{acc['id']}/holdings/{holding_id}")
    assert resp.status_code == 200
    assert resp.json()["holdings"] == []


def test_delete_holding_account_not_found():
    resp = client.delete("/api/accounts/nonexistent-acct/holdings/some-hid")
    assert resp.status_code == 404


def test_delete_holding_not_found():
    acc = _create_account({"name": "Brokerage", "account_type": "taxable"})
    resp = client.delete(f"/api/accounts/{acc['id']}/holdings/nonexistent-hid")
    assert resp.status_code == 404


# ── Portfolio summary ─────────────────────────────────────────────────────

def test_summary_zeros_when_no_accounts():
    resp = client.get("/api/accounts/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["taxable_value"] == 0.0
    assert body["taxable_basis"] == 0.0
    assert body["taxable_unrealized_gain"] == 0.0
    assert body["traditional_balance"] == 0.0
    assert body["roth_balance"] == 0.0
    assert body["hsa_balance"] == 0.0
    assert body["hsa_annual_contribution"] == 0.0
    assert body["total_portfolio_value"] == 0.0


def test_summary_correct_aggregates():
    # Taxable: VTI basis=20k/value=25k, VXUS basis=10k/value=11k
    acc_t = _create_account({"name": "Brokerage", "account_type": "taxable"})
    _add_holding(acc_t["id"], "VTI",  20000.0, 25000.0)
    _add_holding(acc_t["id"], "VXUS", 10000.0, 11000.0)
    _create_account({"name": "401k",     "account_type": "traditional", "balance": 100000.0})
    _create_account({"name": "Roth IRA", "account_type": "roth",        "balance": 50000.0})
    _create_account({
        "name": "HSA", "account_type": "hsa",
        "balance": 10000.0, "annual_contribution": 4000.0,
    })

    body = client.get("/api/accounts/summary").json()
    assert body["taxable_value"]           == 36000.0   # 25000 + 11000
    assert body["taxable_basis"]           == 30000.0   # 20000 + 10000
    assert body["taxable_unrealized_gain"] == 6000.0    # 5000  +  1000
    assert body["traditional_balance"]     == 100000.0
    assert body["roth_balance"]            == 50000.0
    assert body["hsa_balance"]             == 10000.0
    assert body["hsa_annual_contribution"] == 4000.0
    assert body["total_portfolio_value"]   == 196000.0  # 36k+100k+50k+10k


# ── Derived fields ────────────────────────────────────────────────────────

def test_unrealized_gain_correct_per_holding():
    acc = _create_account({"name": "Brokerage", "account_type": "taxable"})
    updated = _add_holding(acc["id"], "GOOGL", 5000.0, 8000.0)
    h = updated["holdings"][0]
    assert h["unrealized_gain"] == 3000.0   # 8000 − 5000


def test_taxable_account_derived_totals():
    acc = _create_account({"name": "Brokerage", "account_type": "taxable"})
    _add_holding(acc["id"], "A", 1000.0, 1500.0)
    _add_holding(acc["id"], "B", 2000.0, 2200.0)

    body = client.get(f"/api/accounts/{acc['id']}").json()
    assert body["total_basis"]           == 3000.0   # 1000 + 2000
    assert body["total_value"]           == 3700.0   # 1500 + 2200
    assert body["total_unrealized_gain"] == 700.0    #  500 +  200
