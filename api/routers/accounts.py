"""Accounts route — thin wrapper around the accounts service."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response

import services.accounts as svc
from api.models.accounts import (
    AccountIn,
    AccountOut,
    HoldingIn,
    HoldingOut,
    PortfolioSummary,
)

router = APIRouter()


def _dec(v: float) -> Decimal:
    return Decimal(str(v))


def _dec_or_none(v: float | None) -> Decimal | None:
    return Decimal(str(v)) if v is not None else None


def _holding_to_response(h: svc.HoldingOut) -> HoldingOut:
    return HoldingOut(
        id=h.id,
        ticker=h.ticker,
        basis=float(h.basis),
        value=float(h.value),
        unrealized_gain=float(h.unrealized_gain),
    )


def _account_to_response(a: svc.AccountOut) -> AccountOut:
    return AccountOut(
        id=a.id,
        name=a.name,
        account_type=a.account_type,
        balance=float(a.balance) if a.balance is not None else None,
        annual_contribution=(
            float(a.annual_contribution) if a.annual_contribution is not None else None
        ),
        holdings=(
            [_holding_to_response(h) for h in a.holdings] if a.holdings is not None else None
        ),
        total_basis=float(a.total_basis) if a.total_basis is not None else None,
        total_value=float(a.total_value) if a.total_value is not None else None,
        total_unrealized_gain=(
            float(a.total_unrealized_gain) if a.total_unrealized_gain is not None else None
        ),
    )


def _to_account_in(req: AccountIn) -> svc.AccountIn:
    return svc.AccountIn(
        name=req.name,
        account_type=req.account_type,
        balance=_dec_or_none(req.balance),
        annual_contribution=_dec_or_none(req.annual_contribution),
    )


def _to_holding_in(req: HoldingIn) -> svc.HoldingIn:
    return svc.HoldingIn(
        ticker=req.ticker,
        basis=_dec(req.basis),
        value=_dec(req.value),
    )


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts():
    return [_account_to_response(a) for a in svc.load_accounts()]


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(request: AccountIn):
    return _account_to_response(svc.create_account(_to_account_in(request)))


@router.get("/accounts/summary", response_model=PortfolioSummary)
def get_summary():
    summary = svc.get_portfolio_summary()
    return PortfolioSummary(
        taxable_value=float(summary.taxable_value),
        taxable_basis=float(summary.taxable_basis),
        taxable_unrealized_gain=float(summary.taxable_unrealized_gain),
        traditional_balance=float(summary.traditional_balance),
        roth_balance=float(summary.roth_balance),
        hsa_balance=float(summary.hsa_balance),
        hsa_annual_contribution=float(summary.hsa_annual_contribution),
        total_portfolio_value=float(summary.total_portfolio_value),
    )


@router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(account_id: str):
    try:
        return _account_to_response(svc.get_account(account_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: str, request: AccountIn):
    try:
        return _account_to_response(svc.update_account(account_id, _to_account_in(request)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: str):
    try:
        svc.delete_account(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(status_code=204)


@router.post("/accounts/{account_id}/holdings", response_model=AccountOut, status_code=201)
def create_holding(account_id: str, request: HoldingIn):
    try:
        return _account_to_response(svc.create_holding(account_id, _to_holding_in(request)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/accounts/{account_id}/holdings/{holding_id}", response_model=AccountOut)
def update_holding(account_id: str, holding_id: str, request: HoldingIn):
    try:
        return _account_to_response(
            svc.update_holding(account_id, holding_id, _to_holding_in(request))
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/accounts/{account_id}/holdings/{holding_id}", response_model=AccountOut)
def delete_holding(account_id: str, holding_id: str):
    try:
        return _account_to_response(svc.delete_holding(account_id, holding_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
