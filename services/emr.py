"""Effective Marginal Rate (EMR) service.

Computes the effective marginal tax rate on each incremental dollar of income
across a sweep range. Composes federal_tax, social_security, and ohio_tax
services — never reimplements their logic.

Returns an array of (income, emr, component_breakdown) points suitable for
visualization and withdrawal decision support.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TypedDict

from services.aged_deduction import additional_standard_deduction
from services.common import round_rate, round_tax
from services.data_loader import (
    get_default_sweep_ceiling_bracket_rate,
    get_default_sweep_step,
    get_planning_bracket_rates,
    get_provisional_income_benefit_rate,
    load_federal_data,
    load_ohio_data,
    load_ss_data,
    require_supported_filing_status,
)
from services.federal_tax import (
    calculate_federal_tax,
    marginal_rate_of_next_dollar,
    split_taxable_income,
    unused_deduction,
)
from services.income_inputs import IncomeInputs
from services.niit import compute_niit, load_niit_parameters
from services.ohio_tax import calculate_ohio_tax
from services.senior_deduction import senior_deduction
from services.social_security import calculate_social_security_taxability

_ZERO = Decimal("0")
_EMR_COMPUTE_STEP = Decimal(
    "500"
)  # smooths whole-dollar rounding noise while preserving bracket-edge precision


class SweepMode(Enum):
    ORDINARY = "ordinary"
    PREFERENTIAL = "preferential"


@dataclass
class EMRPoint:
    income: Decimal
    total_tax: Decimal
    emr: Decimal
    emr_ordinary: Decimal
    emr_ss_torpedo: Decimal
    emr_pref_stacking: Decimal
    emr_niit: Decimal
    emr_ohio: Decimal
    ohio_tax: Decimal
    ss_taxable: Decimal
    ss_inclusion_rate: Decimal
    taxable_ordinary: Decimal
    taxable_preferential: Decimal
    irmaa_magi: Decimal


@dataclass
class EMRResult:
    sweep_mode: SweepMode
    points: list[EMRPoint]
    irmaa_thresholds: list[Decimal]
    tax_year: int
    filing_status: str


@dataclass
class _TaxSnapshot:
    total_ordinary: Decimal
    total_preferential: Decimal
    ss_taxable: Decimal
    ss_inclusion_rate: Decimal
    agi: Decimal
    taxable_ordinary: Decimal
    taxable_preferential: Decimal
    ordinary_tax: Decimal
    preferential_tax: Decimal
    marginal_bracket_rate: Decimal
    next_dollar_ordinary_rate: Decimal
    niit: Decimal
    ohio_tax: Decimal
    total_tax: Decimal


def _get_standard_deduction(
    income: IncomeInputs, filing_status: str, tax_year: int, magi: Decimal
) -> Decimal:
    """The standard deduction, increased for filers aged 65 or older.

    Includes the senior deduction, which depends on income: it is evaluated once at
    ``magi`` (the sweep's starting income), so it does not change along the sweep.
    """
    base = Decimal(load_federal_data(tax_year)["standard_deduction"][filing_status])
    return (
        base
        + additional_standard_deduction(income, filing_status, tax_year)
        + senior_deduction(income, filing_status, tax_year, magi)
    )


def _agi_at_point(
    sweep_value: Decimal,
    sweep_mode: SweepMode,
    income: IncomeInputs,
    variable_ordinary: Decimal,
    filing_status: str,
) -> Decimal:
    """AGI at a sweep point (deductions do not change it)."""
    total_ordinary, total_preferential = _compute_incomes_at_point(
        sweep_value, sweep_mode, income, variable_ordinary
    )
    ss_taxable, _ = _compute_ss_at_point(total_ordinary, total_preferential, income, filing_status)
    return total_ordinary + ss_taxable + total_preferential - income.above_the_line_adjustments


def _get_irmaa_thresholds(filing_status: str, tax_year: int) -> list[Decimal]:
    return [Decimal(t) for t in load_federal_data(tax_year)["irmaa_thresholds"][filing_status]]


def get_default_sweep_ceiling(filing_status: str, tax_year: int) -> Decimal:
    """Return the top of the ordinary bracket configured as the default sweep ceiling."""
    ceiling_rate = get_default_sweep_ceiling_bracket_rate()
    for bracket in load_federal_data(tax_year)["ordinary"][filing_status]:
        if Decimal(bracket["rate"]) == ceiling_rate:
            return Decimal(bracket["to"])
    raise ValueError(f"No {ceiling_rate} ordinary bracket found for {filing_status} {tax_year}")


# ---------------------------------------------------------------------------
# Income helpers
# ---------------------------------------------------------------------------


def _compute_incomes_at_point(
    sweep_value: Decimal,
    sweep_mode: SweepMode,
    income: IncomeInputs,
    variable_ordinary: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (total_ordinary, total_preferential) at a sweep point."""
    if sweep_mode == SweepMode.ORDINARY:
        return income.fixed_ordinary + sweep_value, income.fixed_preferential
    return income.fixed_ordinary + variable_ordinary, income.fixed_preferential + sweep_value


# ---------------------------------------------------------------------------
# Social Security at a point
# ---------------------------------------------------------------------------


def _compute_ss_at_point(
    total_ordinary: Decimal,
    total_preferential: Decimal,
    income: IncomeInputs,
    filing_status: str,
) -> tuple[Decimal, Decimal]:
    """Return (ss_taxable, ss_inclusion_rate)."""
    if income.ss_benefit == _ZERO:
        return _ZERO, _ZERO
    agi_excluding_ss = total_ordinary + total_preferential - income.above_the_line_adjustments
    result = calculate_social_security_taxability(
        ss_benefit=income.ss_benefit,
        agi_excluding_ss=agi_excluding_ss,
        tax_exempt_interest=income.tax_exempt_interest,
        filing_status=filing_status,
    )
    return result.taxable_ss, result.inclusion_rate


# ---------------------------------------------------------------------------
# AGI and taxable income
# ---------------------------------------------------------------------------


def _compute_agi_and_taxable(
    total_ordinary: Decimal,
    ss_taxable: Decimal,
    total_preferential: Decimal,
    std_deduction: Decimal,
    income: IncomeInputs,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (agi, taxable_ordinary, taxable_preferential).

    Deductions that exceed ordinary income reduce preferential income.
    """
    adjustments = income.above_the_line_adjustments
    agi = total_ordinary + ss_taxable + total_preferential - adjustments
    taxable_ordinary, taxable_preferential = split_taxable_income(
        total_ordinary + ss_taxable,
        total_preferential,
        std_deduction + income.additional_deductions + adjustments,
    )
    return agi, taxable_ordinary, taxable_preferential


# ---------------------------------------------------------------------------
# Ohio tax at a point
# ---------------------------------------------------------------------------


def _compute_ohio_tax_at_point(
    agi: Decimal,
    ss_taxable: Decimal,
    ohio_medical_deduction: Decimal,
    ohio_qualifying_retirement_income: Decimal,
    tax_year: int,
    filing_status: str,
) -> Decimal:
    """Compute Ohio tax, reverse-engineering gross medical for fixed deduction."""
    ohio_floor_rate = Decimal(load_ohio_data(tax_year)["medical_expense_floor_rate"])
    ohio_agi = agi - ss_taxable
    medical_floor = round_tax(ohio_agi * ohio_floor_rate)
    gross_medical = ohio_medical_deduction + medical_floor

    result = calculate_ohio_tax(
        federal_agi=agi,
        gross_medical_expenses=gross_medical,
        qualifying_retirement_income=ohio_qualifying_retirement_income,
        ss_taxable_federal=ss_taxable,
        tax_year=tax_year,
        filing_status=filing_status,
    )
    return result.ohio_tax


# ---------------------------------------------------------------------------
# Full tax snapshot at a single sweep point
# ---------------------------------------------------------------------------


class _SnapshotKwargs(TypedDict, total=False):
    sweep_mode: SweepMode
    income: IncomeInputs
    variable_ordinary: Decimal
    std_deduction: Decimal
    niit_threshold: Decimal
    niit_rate: Decimal
    filing_status: str
    tax_year: int
    include_ohio: bool
    ohio_medical_deduction: Decimal
    ohio_qualifying_retirement_income: Decimal


def _next_dollar_ordinary_rate(
    total_ordinary_after_ss: Decimal,
    taxable_ordinary: Decimal,
    std_deduction: Decimal,
    income: IncomeInputs,
    filing_status: str,
    tax_year: int,
) -> Decimal:
    """Ordinary tax rate on the next dollar: zero while deductions still shelter it."""
    deductions = std_deduction + income.additional_deductions + income.above_the_line_adjustments
    if unused_deduction(total_ordinary_after_ss, deductions) > _ZERO:
        return _ZERO
    brackets = load_federal_data(tax_year)["ordinary"][filing_status]
    return marginal_rate_of_next_dollar(taxable_ordinary, brackets)


def _compute_tax_snapshot(
    sweep_value: Decimal,
    sweep_mode: SweepMode,
    income: IncomeInputs,
    variable_ordinary: Decimal,
    std_deduction: Decimal,
    niit_threshold: Decimal,
    niit_rate: Decimal,
    filing_status: str,
    tax_year: int,
    include_ohio: bool,
    ohio_medical_deduction: Decimal,
    ohio_qualifying_retirement_income: Decimal,
) -> _TaxSnapshot:
    """Compute complete tax at a single sweep point."""
    total_ordinary, total_preferential = _compute_incomes_at_point(
        sweep_value, sweep_mode, income, variable_ordinary
    )

    ss_taxable, ss_inclusion_rate = _compute_ss_at_point(
        total_ordinary, total_preferential, income, filing_status
    )

    agi, taxable_ordinary, taxable_preferential = _compute_agi_and_taxable(
        total_ordinary, ss_taxable, total_preferential, std_deduction, income
    )

    fed_result = calculate_federal_tax(
        ordinary_income=taxable_ordinary,
        preferential_income=taxable_preferential,
        filing_status=filing_status,
        tax_year=tax_year,
    )

    net_investment_income = income.investment_ordinary + total_preferential
    niit = compute_niit(agi, net_investment_income, niit_threshold, niit_rate)

    ohio_tax = _ZERO
    if include_ohio:
        ohio_tax = _compute_ohio_tax_at_point(
            agi,
            ss_taxable,
            ohio_medical_deduction,
            ohio_qualifying_retirement_income,
            tax_year,
            filing_status=filing_status,
        )

    total_tax = fed_result.total_tax + niit + ohio_tax

    return _TaxSnapshot(
        total_ordinary=total_ordinary,
        total_preferential=total_preferential,
        ss_taxable=ss_taxable,
        ss_inclusion_rate=ss_inclusion_rate,
        agi=agi,
        taxable_ordinary=taxable_ordinary,
        taxable_preferential=taxable_preferential,
        ordinary_tax=fed_result.ordinary_income_tax,
        preferential_tax=fed_result.preferential_income_tax,
        marginal_bracket_rate=fed_result.marginal_bracket_rate,
        next_dollar_ordinary_rate=_next_dollar_ordinary_rate(
            total_ordinary + ss_taxable,
            taxable_ordinary,
            std_deduction,
            income,
            filing_status,
            tax_year,
        ),
        niit=niit,
        ohio_tax=ohio_tax,
        total_tax=total_tax,
    )


# ---------------------------------------------------------------------------
# EMR between two points
# ---------------------------------------------------------------------------


def _compute_emr_between_points(lo: _TaxSnapshot, hi: _TaxSnapshot, step: Decimal) -> Decimal:
    """Return total EMR from the tax difference between two snapshots."""
    return round_rate((hi.total_tax - lo.total_tax) / step)


def _attribute_emr_components(
    lo: _TaxSnapshot,
    hi: _TaxSnapshot,
    step: Decimal,
    sweep_mode: SweepMode,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Return (emr_ordinary, emr_ss_torpedo, emr_pref_stacking, emr_niit, emr_ohio).

    emr_ordinary is the ordinary rate on the next dollar at the sweep point (ORDINARY
    mode) or zero (PREFERENTIAL mode): zero while deductions still shelter ordinary
    income, then the rate of the bracket that dollar falls in. It is taken at the point
    itself, not from tax 500 dollars ahead, so a bracket starts exactly where taxable
    income reaches it. Components sum to emr within rounding tolerance.
    """
    bracket_rate = lo.marginal_bracket_rate

    emr_ordinary = lo.next_dollar_ordinary_rate if sweep_mode == SweepMode.ORDINARY else _ZERO

    ss_delta = (hi.ss_taxable - lo.ss_taxable) / step
    emr_ss_torpedo = round_rate(bracket_rate * ss_delta)

    emr_pref_stacking = round_rate((hi.preferential_tax - lo.preferential_tax) / step)
    emr_niit = round_rate((hi.niit - lo.niit) / step)
    emr_ohio = round_rate((hi.ohio_tax - lo.ohio_tax) / step)

    return emr_ordinary, emr_ss_torpedo, emr_pref_stacking, emr_niit, emr_ohio


# ---------------------------------------------------------------------------
# Sweep array construction
# ---------------------------------------------------------------------------


def _build_regular_sweep(floor: Decimal, ceiling: Decimal, step: Decimal) -> list[Decimal]:
    """Generate regular sweep points from floor to ceiling."""
    points: list[Decimal] = []
    current = floor
    while current <= ceiling:
        points.append(current)
        current += step
    return points


def _compute_ohio_boundaries(
    ohio_agi_base: Decimal,
    ohio_medical_deduction: Decimal,
    tax_year: int,
    filing_status: str,
) -> list[Decimal]:
    """Return Ohio-specific boundary sweep_values for zero-rate and MAGI credit thresholds.

    ohio_agi_base is total non-SS income at sweep_value=0 (ohio_agi = ohio_agi_base + sweep_value).
    Boundary points are approximate — ohio_medical_deduction is included in the zero-rate
    threshold but personal exemption is taken from the expected tier at each boundary.
    """
    ohio_data = load_ohio_data(tax_year)
    exemption_key = f"personal_exemption_{filing_status}"
    boundaries: list[Decimal] = []

    # Zero-rate threshold: ohio_tax_base enters the first taxable bracket
    # ohio_tax_base = ohio_agi - personal_exemption - ohio_medical_deduction = brackets[1]["from"]
    # At this ohio_agi the personal_exemption is from the lowest exemption tier
    zero_bracket = Decimal(ohio_data["brackets"][1]["from"])
    exemption_low = Decimal(ohio_data[exemption_key][0]["amount"])
    ohio_agi_zero = zero_bracket + exemption_low + ohio_medical_deduction
    boundaries.append(ohio_agi_zero - ohio_agi_base)

    # MAGI credit threshold: ohio_agi - personal_exemption crosses magi_credit_threshold
    # At this ohio_agi the personal_exemption is the highest non-zero tier
    magi_threshold = Decimal(ohio_data["magi_credit_threshold"])
    exemption_high = Decimal(
        ohio_data[exemption_key][-2]["amount"]
    )  # -2: skip the zero-amount sentinel tier
    ohio_agi_magi = magi_threshold + exemption_high
    boundaries.append(ohio_agi_magi - ohio_agi_base)

    return boundaries


def _compute_ordinary_boundaries(
    income: IncomeInputs,
    std_deduction: Decimal,
    niit_threshold: Decimal,
    filing_status: str,
    tax_year: int,
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
) -> list[Decimal]:
    """Compute approximate boundary points for ORDINARY sweep mode."""
    data = load_federal_data(tax_year)
    boundaries: list[Decimal] = []
    total_deduction = (
        std_deduction + income.additional_deductions + income.above_the_line_adjustments
    )

    # Standard deduction exhaustion
    boundaries.append(total_deduction - income.fixed_ordinary)

    # Ordinary bracket boundaries
    for bracket in data["ordinary"][filing_status]:
        if bracket["to"] is not None:
            b_to = Decimal(bracket["to"])
            boundaries.append(b_to + total_deduction - income.fixed_ordinary)

    # Preferential stacking boundaries
    if income.fixed_preferential > _ZERO:
        for bracket in data["preferential"][filing_status]:
            if bracket["to"] is not None:
                p_to = Decimal(bracket["to"])
                boundaries.append(
                    p_to - income.fixed_preferential + total_deduction - income.fixed_ordinary
                )
                boundaries.append(p_to + total_deduction - income.fixed_ordinary)

    # SS torpedo boundaries
    if income.ss_benefit > _ZERO:
        half_ss = income.ss_benefit * get_provisional_income_benefit_rate()
        base_prov = (
            income.fixed_ordinary
            + income.fixed_preferential
            - income.above_the_line_adjustments
            + income.tax_exempt_interest
            + half_ss
        )
        ss_data = load_ss_data()
        tier_1 = Decimal(ss_data[filing_status]["tier_1_threshold"])
        tier_2 = Decimal(ss_data[filing_status]["tier_2_threshold"])
        boundaries.append(tier_1 - base_prov)
        boundaries.append(tier_2 - base_prov)

        tier_1_rate = Decimal(ss_data["tier_1_inclusion_rate"])
        tier_2_rate = Decimal(ss_data["tier_2_inclusion_rate"])
        max_rate = Decimal(ss_data["maximum_inclusion_rate"])
        max_tier_1 = min(tier_1_rate * income.ss_benefit, tier_1_rate * (tier_2 - tier_1))
        max_taxable = max_rate * income.ss_benefit
        if max_taxable > max_tier_1:
            ss_max_prov = tier_2 + round_tax((max_taxable - max_tier_1) / tier_2_rate)
            boundaries.append(ss_max_prov - base_prov)

    # NIIT threshold (approximate — ignores ss_taxable in AGI)
    boundaries.append(niit_threshold - income.fixed_ordinary - income.fixed_preferential)

    # Ohio discontinuity boundaries
    if include_ohio:
        ohio_agi_base = income.fixed_ordinary + income.fixed_preferential
        boundaries.extend(
            _compute_ohio_boundaries(ohio_agi_base, ohio_medical_deduction, tax_year, filing_status)
        )

    return boundaries


def _compute_preferential_boundaries(
    income: IncomeInputs,
    variable_ordinary: Decimal,
    std_deduction: Decimal,
    niit_threshold: Decimal,
    filing_status: str,
    tax_year: int,
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
) -> list[Decimal]:
    """Compute approximate boundary points for PREFERENTIAL sweep mode."""
    data = load_federal_data(tax_year)
    boundaries: list[Decimal] = []

    total_ordinary = income.fixed_ordinary + variable_ordinary
    total_deduction = (
        std_deduction + income.additional_deductions + income.above_the_line_adjustments
    )
    taxable_ordinary, _ = split_taxable_income(total_ordinary, _ZERO, total_deduction)
    excess_deduction = unused_deduction(total_ordinary, total_deduction)
    fixed_pref = income.fixed_preferential

    # Preferential bracket boundaries
    for bracket in data["preferential"][filing_status]:
        if bracket["to"] is not None:
            p_to = Decimal(bracket["to"])
            boundaries.append(p_to - taxable_ordinary - fixed_pref + excess_deduction)

    # SS torpedo boundaries
    if income.ss_benefit > _ZERO:
        half_ss = income.ss_benefit * get_provisional_income_benefit_rate()
        base_prov = (
            total_ordinary
            + fixed_pref
            - income.above_the_line_adjustments
            + income.tax_exempt_interest
            + half_ss
        )
        ss_data = load_ss_data()
        tier_1 = Decimal(ss_data[filing_status]["tier_1_threshold"])
        tier_2 = Decimal(ss_data[filing_status]["tier_2_threshold"])
        boundaries.append(tier_1 - base_prov)
        boundaries.append(tier_2 - base_prov)

        tier_1_rate = Decimal(ss_data["tier_1_inclusion_rate"])
        tier_2_rate = Decimal(ss_data["tier_2_inclusion_rate"])
        max_rate = Decimal(ss_data["maximum_inclusion_rate"])
        max_tier_1 = min(tier_1_rate * income.ss_benefit, tier_1_rate * (tier_2 - tier_1))
        max_taxable = max_rate * income.ss_benefit
        if max_taxable > max_tier_1:
            ss_max_prov = tier_2 + round_tax((max_taxable - max_tier_1) / tier_2_rate)
            boundaries.append(ss_max_prov - base_prov)

    # NIIT threshold (approximate)
    boundaries.append(niit_threshold - total_ordinary - fixed_pref)

    # Ohio discontinuity boundaries
    if include_ohio:
        ohio_agi_base = total_ordinary + fixed_pref
        boundaries.extend(
            _compute_ohio_boundaries(ohio_agi_base, ohio_medical_deduction, tax_year, filing_status)
        )

    return boundaries


def _insert_boundary_points(
    regular_points: list[Decimal],
    boundary_points: list[Decimal],
    floor: Decimal,
    ceiling: Decimal,
) -> list[Decimal]:
    """Merge boundary points into regular sweep, deduplicate and sort."""
    valid = [round_tax(b) for b in boundary_points if floor <= b <= ceiling]
    all_points = set(regular_points) | set(valid)
    return sorted(all_points)


def _build_sweep_array(
    floor: Decimal,
    ceiling: Decimal,
    step: Decimal,
    boundary_points: list[Decimal],
) -> list[Decimal]:
    """Build the complete sweep array with regular and boundary points."""
    regular = _build_regular_sweep(floor, ceiling, step)
    return _insert_boundary_points(regular, boundary_points, floor, ceiling)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_emr(
    *,
    income: IncomeInputs,
    sweep_mode: SweepMode,
    filing_status: str,
    tax_year: int,
    variable_ordinary: Decimal = _ZERO,
    sweep_floor: Decimal = _ZERO,
    sweep_ceiling: Decimal | None = None,
    sweep_step: Decimal | None = None,
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
    ohio_qualifying_retirement_income: Decimal = _ZERO,
    extra_boundary_points: list[Decimal] | None = None,
) -> EMRResult:
    """Sweep EMR across an income range.

    ``income`` holds the forced income and adjustments. Its ``other_investment_ordinary``
    is ordinary income that is also net investment income for NIIT (rental, royalties,
    non-qualified annuity earnings, short-term gains); pension, IRA, and similar
    distributions are not net investment income.
    """
    require_supported_filing_status(filing_status)

    # Load data-driven defaults
    floor_agi = _agi_at_point(sweep_floor, sweep_mode, income, variable_ordinary, filing_status)
    std_deduction = _get_standard_deduction(income, filing_status, tax_year, floor_agi)
    niit_threshold, niit_rate = load_niit_parameters(filing_status, tax_year)
    irmaa_thresholds = _get_irmaa_thresholds(filing_status, tax_year)

    if sweep_ceiling is None:
        sweep_ceiling = get_default_sweep_ceiling(filing_status, tax_year)
    if sweep_step is None:
        sweep_step = get_default_sweep_step()

    # Compute boundary points
    if sweep_mode == SweepMode.ORDINARY:
        boundaries = _compute_ordinary_boundaries(
            income,
            std_deduction,
            niit_threshold,
            filing_status,
            tax_year,
            include_ohio=include_ohio,
            ohio_medical_deduction=ohio_medical_deduction,
        )
    else:
        boundaries = _compute_preferential_boundaries(
            income,
            variable_ordinary,
            std_deduction,
            niit_threshold,
            filing_status,
            tax_year,
            include_ohio=include_ohio,
            ohio_medical_deduction=ohio_medical_deduction,
        )

    if extra_boundary_points:
        boundaries.extend(extra_boundary_points)

    sweep_array = _build_sweep_array(sweep_floor, sweep_ceiling, sweep_step, boundaries)

    # Shared keyword args for _compute_tax_snapshot
    shared: _SnapshotKwargs = dict(
        sweep_mode=sweep_mode,
        income=income,
        variable_ordinary=variable_ordinary,
        std_deduction=std_deduction,
        niit_threshold=niit_threshold,
        niit_rate=niit_rate,
        filing_status=filing_status,
        tax_year=tax_year,
        include_ohio=include_ohio,
        ohio_medical_deduction=ohio_medical_deduction,
        ohio_qualifying_retirement_income=ohio_qualifying_retirement_income,
    )

    points: list[EMRPoint] = []
    for sweep_value in sweep_array:
        lo = _compute_tax_snapshot(sweep_value, **shared)
        hi = _compute_tax_snapshot(sweep_value + _EMR_COMPUTE_STEP, **shared)

        emr = _compute_emr_between_points(lo, hi, _EMR_COMPUTE_STEP)
        (emr_ordinary, emr_ss_torpedo, emr_pref_stacking, emr_niit, emr_ohio) = (
            _attribute_emr_components(lo, hi, _EMR_COMPUTE_STEP, sweep_mode)
        )

        points.append(
            EMRPoint(
                income=sweep_value,
                total_tax=lo.total_tax,
                emr=emr,
                emr_ordinary=emr_ordinary,
                emr_ss_torpedo=emr_ss_torpedo,
                emr_pref_stacking=emr_pref_stacking,
                emr_niit=emr_niit,
                emr_ohio=emr_ohio,
                ohio_tax=lo.ohio_tax,
                ss_taxable=lo.ss_taxable,
                ss_inclusion_rate=lo.ss_inclusion_rate,
                taxable_ordinary=lo.taxable_ordinary,
                taxable_preferential=lo.taxable_preferential,
                irmaa_magi=lo.agi + income.tax_exempt_interest,
            )
        )

    return EMRResult(
        sweep_mode=sweep_mode,
        points=points,
        irmaa_thresholds=irmaa_thresholds,
        tax_year=tax_year,
        filing_status=filing_status,
    )


# ---------------------------------------------------------------------------
# Planning signals — computed from EMR results + input parameters
# ---------------------------------------------------------------------------


@dataclass
class BracketDistance:
    """Income needed, from the sweep floor, for ordinary EMR to reach a bracket rate."""

    rate: Decimal
    distance: Decimal | None


@dataclass
class PlanningSignals:
    zero_ordinary_space: Decimal | None
    ltcg_0pct_remaining: Decimal | None
    ltcg_0pct_ordinary_runway: Decimal | None
    torpedo_active: bool
    ss_fully_taxable: bool
    bracket_distances: list[BracketDistance]


def _get_ltcg_0pct_ceiling(filing_status: str, tax_year: int) -> Decimal:
    data = load_federal_data(tax_year)
    return Decimal(data["preferential"][filing_status][0]["to"])


def _compute_ltcg_0pct_remaining(
    points: list[EMRPoint],
    filing_status: str,
    tax_year: int,
) -> Decimal | None:
    """Room left under the 0% gains bracket, whether or not gains are already entered."""
    if not points:
        return None
    ceiling = _get_ltcg_0pct_ceiling(filing_status, tax_year)
    taxable_income_at_floor = points[0].taxable_ordinary + points[0].taxable_preferential
    remaining = ceiling - taxable_income_at_floor
    return remaining if remaining > _ZERO else None


def _compute_ltcg_0pct_ordinary_runway(
    points: list[EMRPoint],
    sweep_mode: SweepMode,
    income: IncomeInputs,
    ss_taxable_at_floor: Decimal,
    std_deduction: Decimal,
    filing_status: str,
    tax_year: int,
) -> Decimal | None:
    """Additional ordinary income before existing LTCG leaves the 0% LTCG bracket."""
    ltcg_already_used = income.fixed_preferential
    if not points:
        return None
    if sweep_mode == SweepMode.ORDINARY and ltcg_already_used == _ZERO:
        return None
    ceiling = _get_ltcg_0pct_ceiling(filing_status, tax_year)
    runway = (
        ceiling
        - ltcg_already_used
        + std_deduction
        + income.above_the_line_adjustments
        + income.additional_deductions
        - income.fixed_ordinary
        - ss_taxable_at_floor
    )
    return runway if runway > _ZERO else None


def _compute_zero_ordinary_space(
    points: list[EMRPoint],
    sweep_mode: SweepMode,
    income: IncomeInputs,
    variable_ordinary: Decimal,
    ss_taxable_at_floor: Decimal,
    std_deduction: Decimal,
) -> Decimal | None:
    if not points:
        return None
    effective_fixed = income.fixed_ordinary
    if sweep_mode == SweepMode.PREFERENTIAL:
        effective_fixed += variable_ordinary
    return max(
        _ZERO,
        std_deduction
        + income.above_the_line_adjustments
        + income.additional_deductions
        - effective_fixed
        - ss_taxable_at_floor,
    )


def _distance_to_rate(points: list[EMRPoint], rate: Decimal) -> Decimal | None:
    """Return income above the floor at which ordinary EMR first reaches the rate, if ahead."""
    floor_income = points[0].income
    if points[0].emr_ordinary >= rate:
        return None  # already at or past this bracket
    for p in points:
        if p.emr_ordinary >= rate:
            return p.income - floor_income
    return None


def _compute_bracket_distances(
    points: list[EMRPoint], rates: list[Decimal]
) -> list[BracketDistance]:
    return [
        BracketDistance(rate=rate, distance=_distance_to_rate(points, rate) if points else None)
        for rate in rates
    ]


def compute_planning_signals(
    result: EMRResult,
    *,
    income: IncomeInputs,
    variable_ordinary: Decimal,
) -> PlanningSignals:
    """Compute planning signals from an EMR result and the income it was run with."""
    pts = result.points
    floor_agi = pts[0].irmaa_magi - income.tax_exempt_interest if pts else _ZERO
    std_deduction = _get_standard_deduction(
        income, result.filing_status, result.tax_year, floor_agi
    )
    ltcg_already_used = income.fixed_preferential
    ss_taxable_at_floor = pts[0].ss_taxable if pts else _ZERO

    zero_ordinary_space = _compute_zero_ordinary_space(
        pts,
        result.sweep_mode,
        income,
        variable_ordinary,
        ss_taxable_at_floor,
        std_deduction,
    )

    ltcg_0pct_remaining = _compute_ltcg_0pct_remaining(
        pts,
        result.filing_status,
        result.tax_year,
    )

    ltcg_0pct_ordinary_runway = _compute_ltcg_0pct_ordinary_runway(
        pts,
        result.sweep_mode,
        income,
        ss_taxable_at_floor,
        std_deduction,
        result.filing_status,
        result.tax_year,
    )

    torpedo_active = any(p.emr_ss_torpedo > _ZERO for p in pts)
    max_inclusion_rate = Decimal(load_ss_data()["maximum_inclusion_rate"])
    ss_fully_taxable = pts[0].ss_inclusion_rate >= max_inclusion_rate if pts else False

    bracket_distances = _compute_bracket_distances(pts, get_planning_bracket_rates())

    return PlanningSignals(
        zero_ordinary_space=zero_ordinary_space,
        ltcg_0pct_remaining=ltcg_0pct_remaining,
        ltcg_0pct_ordinary_runway=ltcg_0pct_ordinary_runway,
        torpedo_active=torpedo_active,
        ss_fully_taxable=ss_fully_taxable,
        bracket_distances=bracket_distances,
    )
