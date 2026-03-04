"""Shared helpers for the services layer."""

from decimal import ROUND_HALF_UP, Decimal

_DOLLAR = Decimal("1")
_FOUR_PLACES = Decimal("0.0001")


def round_tax(amount: Decimal) -> Decimal:
    """Round a tax amount to the nearest whole dollar using ROUND_HALF_UP."""
    return amount.quantize(_DOLLAR, rounding=ROUND_HALF_UP)


def round_rate(amount: Decimal) -> Decimal:
    """Round a rate to 4 decimal places using ROUND_HALF_UP."""
    return amount.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)