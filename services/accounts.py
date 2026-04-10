"""Account inventory service.

Manages retirement accounts (taxable, traditional, roth, hsa) and their holdings.
Reads from and writes to profile/accounts.json.

Decimal throughout; float only at the JSON boundary.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4

_DATA_PATH = Path(__file__).parent.parent / "profile" / "accounts.json"
_ZERO = Decimal("0")

AccountType = Literal["taxable", "traditional", "roth", "hsa"]


@dataclass
class HoldingIn:
    ticker: str
    basis: Decimal
    value: Decimal


@dataclass
class HoldingOut:
    id: str
    ticker: str
    basis: Decimal
    value: Decimal
    unrealized_gain: Decimal


@dataclass
class AccountIn:
    name: str
    account_type: AccountType
    balance: Decimal | None = None
    annual_contribution: Decimal | None = None


@dataclass
class AccountOut:
    id: str
    name: str
    account_type: str
    balance: Decimal | None
    annual_contribution: Decimal | None
    holdings: list[HoldingOut] | None
    total_basis: Decimal | None
    total_value: Decimal | None
    total_unrealized_gain: Decimal | None


@dataclass
class PortfolioSummary:
    taxable_value: Decimal
    taxable_basis: Decimal
    taxable_unrealized_gain: Decimal
    traditional_balance: Decimal
    roth_balance: Decimal
    hsa_balance: Decimal
    hsa_annual_contribution: Decimal
    total_portfolio_value: Decimal


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def _load_raw(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


def _save_raw(accounts: list[dict], path: Path) -> None:
    with path.open("w") as f:
        json.dump(accounts, f, indent=2)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _holding_out_from_dict(d: dict) -> HoldingOut:
    basis = Decimal(str(d["basis"]))
    value = Decimal(str(d["value"]))
    return HoldingOut(
        id=d["id"],
        ticker=d["ticker"],
        basis=basis,
        value=value,
        unrealized_gain=value - basis,
    )


def _holding_in_to_dict(data: HoldingIn, holding_id: str) -> dict:
    return {
        "id": holding_id,
        "ticker": data.ticker.upper(),
        "basis": float(data.basis),
        "value": float(data.value),
    }


def _account_out_from_dict(d: dict) -> AccountOut:
    holdings: list[HoldingOut] | None = None
    total_basis: Decimal | None = None
    total_value: Decimal | None = None
    total_unrealized_gain: Decimal | None = None

    if d["account_type"] == "taxable":
        holdings = [_holding_out_from_dict(h) for h in (d.get("holdings") or [])]
        total_basis = sum((h.basis for h in holdings), _ZERO)
        total_value = sum((h.value for h in holdings), _ZERO)
        total_unrealized_gain = sum((h.unrealized_gain for h in holdings), _ZERO)

    balance = Decimal(str(d["balance"])) if d.get("balance") is not None else None
    annual_contribution = (
        Decimal(str(d["annual_contribution"])) if d.get("annual_contribution") is not None else None
    )

    return AccountOut(
        id=d["id"],
        name=d["name"],
        account_type=d["account_type"],
        balance=balance,
        annual_contribution=annual_contribution,
        holdings=holdings,
        total_basis=total_basis,
        total_value=total_value,
        total_unrealized_gain=total_unrealized_gain,
    )


def _account_in_to_dict(data: AccountIn, account_id: str) -> dict:
    return {
        "id": account_id,
        "name": data.name,
        "account_type": data.account_type,
        "balance": float(data.balance) if data.balance is not None else None,
        "annual_contribution": (
            float(data.annual_contribution) if data.annual_contribution is not None else None
        ),
        "holdings": [] if data.account_type == "taxable" else None,
    }


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


def load_accounts(_path: Path = _DATA_PATH) -> list[AccountOut]:
    return [_account_out_from_dict(d) for d in _load_raw(_path)]


def get_account(account_id: str, _path: Path = _DATA_PATH) -> AccountOut:
    for d in _load_raw(_path):
        if d["id"] == account_id:
            return _account_out_from_dict(d)
    raise ValueError(f"Account not found: {account_id}")


def create_account(data: AccountIn, _path: Path = _DATA_PATH) -> AccountOut:
    accounts = _load_raw(_path)
    account_dict = _account_in_to_dict(data, str(uuid4()))
    accounts.append(account_dict)
    _save_raw(accounts, _path)
    return _account_out_from_dict(account_dict)


def update_account(account_id: str, data: AccountIn, _path: Path = _DATA_PATH) -> AccountOut:
    accounts = _load_raw(_path)
    for i, d in enumerate(accounts):
        if d["id"] == account_id:
            updated = _account_in_to_dict(data, account_id)
            if data.account_type == "taxable":
                updated["holdings"] = d.get("holdings") or []
            accounts[i] = updated
            _save_raw(accounts, _path)
            return _account_out_from_dict(updated)
    raise ValueError(f"Account not found: {account_id}")


def delete_account(account_id: str, _path: Path = _DATA_PATH) -> None:
    accounts = _load_raw(_path)
    new_accounts = [d for d in accounts if d["id"] != account_id]
    if len(new_accounts) == len(accounts):
        raise ValueError(f"Account not found: {account_id}")
    _save_raw(new_accounts, _path)


def create_holding(account_id: str, data: HoldingIn, _path: Path = _DATA_PATH) -> AccountOut:
    accounts = _load_raw(_path)
    for i, d in enumerate(accounts):
        if d["id"] == account_id:
            if d["account_type"] != "taxable":
                raise ValueError("Holdings are only supported for taxable accounts")
            holdings = d.get("holdings") or []
            holdings.append(_holding_in_to_dict(data, str(uuid4())))
            d["holdings"] = holdings
            accounts[i] = d
            _save_raw(accounts, _path)
            return _account_out_from_dict(d)
    raise ValueError(f"Account not found: {account_id}")


def update_holding(
    account_id: str, holding_id: str, data: HoldingIn, _path: Path = _DATA_PATH
) -> AccountOut:
    accounts = _load_raw(_path)
    for i, d in enumerate(accounts):
        if d["id"] == account_id:
            holdings = d.get("holdings") or []
            for j, h in enumerate(holdings):
                if h["id"] == holding_id:
                    holdings[j] = _holding_in_to_dict(data, holding_id)
                    d["holdings"] = holdings
                    accounts[i] = d
                    _save_raw(accounts, _path)
                    return _account_out_from_dict(d)
            raise ValueError(f"Holding not found: {holding_id}")
    raise ValueError(f"Account not found: {account_id}")


def delete_holding(account_id: str, holding_id: str, _path: Path = _DATA_PATH) -> AccountOut:
    accounts = _load_raw(_path)
    for i, d in enumerate(accounts):
        if d["id"] == account_id:
            holdings = d.get("holdings") or []
            new_holdings = [h for h in holdings if h["id"] != holding_id]
            if len(new_holdings) == len(holdings):
                raise ValueError(f"Holding not found: {holding_id}")
            d["holdings"] = new_holdings
            accounts[i] = d
            _save_raw(accounts, _path)
            return _account_out_from_dict(d)
    raise ValueError(f"Account not found: {account_id}")


def get_portfolio_summary(_path: Path = _DATA_PATH) -> PortfolioSummary:
    accounts = load_accounts(_path)

    taxable_value = _ZERO
    taxable_basis = _ZERO
    taxable_unrealized_gain = _ZERO
    traditional_balance = _ZERO
    roth_balance = _ZERO
    hsa_balance = _ZERO
    hsa_annual_contribution = _ZERO

    for a in accounts:
        if a.account_type == "taxable":
            taxable_value += a.total_value or _ZERO
            taxable_basis += a.total_basis or _ZERO
            taxable_unrealized_gain += a.total_unrealized_gain or _ZERO
        elif a.account_type == "traditional":
            traditional_balance += a.balance or _ZERO
        elif a.account_type == "roth":
            roth_balance += a.balance or _ZERO
        elif a.account_type == "hsa":
            hsa_balance += a.balance or _ZERO
            hsa_annual_contribution += a.annual_contribution or _ZERO

    return PortfolioSummary(
        taxable_value=taxable_value,
        taxable_basis=taxable_basis,
        taxable_unrealized_gain=taxable_unrealized_gain,
        traditional_balance=traditional_balance,
        roth_balance=roth_balance,
        hsa_balance=hsa_balance,
        hsa_annual_contribution=hsa_annual_contribution,
        total_portfolio_value=taxable_value + traditional_balance + roth_balance + hsa_balance,
    )
