"""Social Security taxability service.

Determines the taxable portion of Social Security benefits using the IRS
provisional income formula. Standalone service — no dependency on the
federal_tax or ohio_tax services.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from services.common import round_rate, round_tax
from services.data_loader import load_ss_data

_TWO_PLACES = Decimal("0.01")


@dataclass
class SocialSecurityResult:
    provisional_income: Decimal
    taxable_ss: Decimal
    inclusion_rate: Decimal
    tier: str


def _round2(amount: Decimal) -> Decimal:
    return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _compute_provisional_income(
    agi_excluding_ss: Decimal,
    tax_exempt_interest: Decimal,
    ss_benefit: Decimal,
) -> Decimal:
    half_ss = _round2(ss_benefit * Decimal("0.50"))
    return agi_excluding_ss + tax_exempt_interest + half_ss


def _compute_taxable_ss(
    provisional_income: Decimal,
    ss_benefit: Decimal,
    tier_1_threshold: Decimal,
    tier_2_threshold: Decimal,
    tier_1_rate: Decimal,
    tier_2_rate: Decimal,
    max_rate: Decimal,
) -> tuple[Decimal, str]:
    """Return (taxable_ss, tier) based on provisional income and thresholds."""
    if provisional_income <= tier_1_threshold:
        return Decimal("0"), "none"

    if provisional_income < tier_2_threshold:
        amount = _round2(tier_1_rate * (provisional_income - tier_1_threshold))
        cap = _round2(tier_1_rate * ss_benefit)
        return round_tax(min(amount, cap)), "fifty_percent"

    tier_1_range = tier_2_threshold - tier_1_threshold
    max_tier_1 = min(
        _round2(tier_1_rate * ss_benefit),
        _round2(tier_1_rate * tier_1_range),
    )
    tier_2_amount = _round2(tier_2_rate * (provisional_income - tier_2_threshold))
    max_taxable = _round2(max_rate * ss_benefit)
    return round_tax(min(max_taxable, tier_2_amount + max_tier_1)), "eighty_five_percent"


def calculate_social_security_taxability(
    ss_benefit: Decimal,
    agi_excluding_ss: Decimal,
    tax_exempt_interest: Decimal,
    filing_status: str,
) -> SocialSecurityResult:
    if filing_status not in ("single", "mfj"):
        raise ValueError(f"Unsupported filing status: {filing_status!r}")

    provisional_income = _compute_provisional_income(
        agi_excluding_ss, tax_exempt_interest, ss_benefit
    )

    if ss_benefit == 0:
        return SocialSecurityResult(
            provisional_income=provisional_income,
            taxable_ss=Decimal("0"),
            inclusion_rate=Decimal("0"),
            tier="none",
        )

    thresholds = load_ss_data()
    fs = thresholds[filing_status]
    tier_1 = Decimal(fs["tier_1_threshold"])
    tier_2 = Decimal(fs["tier_2_threshold"])
    tier_1_rate = Decimal(thresholds["tier_1_inclusion_rate"])
    tier_2_rate = Decimal(thresholds["tier_2_inclusion_rate"])
    max_rate = Decimal(thresholds["maximum_inclusion_rate"])

    taxable_ss, tier = _compute_taxable_ss(
        provisional_income, ss_benefit, tier_1, tier_2, tier_1_rate, tier_2_rate, max_rate
    )
    inclusion_rate = round_rate(taxable_ss / ss_benefit)

    return SocialSecurityResult(
        provisional_income=provisional_income,
        taxable_ss=taxable_ss,
        inclusion_rate=inclusion_rate,
        tier=tier,
    )
