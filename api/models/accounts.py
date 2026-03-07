"""Pydantic models for the accounts route."""

from typing import Literal

from pydantic import BaseModel, Field


class HoldingIn(BaseModel):
    ticker: str = Field(min_length=1)
    basis: float = Field(ge=0)
    value: float = Field(ge=0)


class HoldingOut(BaseModel):
    id: str
    ticker: str
    basis: float
    value: float
    unrealized_gain: float


class AccountIn(BaseModel):
    name: str = Field(min_length=1)
    account_type: Literal["taxable", "traditional", "roth", "hsa"]
    balance: float | None = Field(default=None, ge=0)
    annual_contribution: float | None = Field(default=None, ge=0)


class AccountOut(BaseModel):
    id: str
    name: str
    account_type: str
    balance: float | None
    annual_contribution: float | None
    holdings: list[HoldingOut] | None
    total_basis: float | None
    total_value: float | None
    total_unrealized_gain: float | None


class PortfolioSummary(BaseModel):
    taxable_value: float
    taxable_basis: float
    taxable_unrealized_gain: float
    traditional_balance: float
    roth_balance: float
    hsa_balance: float
    hsa_annual_contribution: float
    total_portfolio_value: float
