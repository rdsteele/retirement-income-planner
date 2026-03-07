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
from functools import lru_cache
from pathlib import Path
import json

from services.common import round_rate, round_tax
from services.federal_tax import calculate_federal_tax
from services.ohio_tax import calculate_ohio_tax
from services.social_security import calculate_social_security_taxability

_DATA_DIR = Path(__file__).parent.parent / "data" / "brackets"
_SS_PATH = Path(__file__).parent.parent / "data" / "ss_thresholds.json"
_ZERO = Decimal("0")
_HALF = Decimal("0.50")
_EMR_COMPUTE_STEP = Decimal("1000")  # larger step reduces whole-dollar rounding noise


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
    ordinary_tax: Decimal
    preferential_tax: Decimal
    marginal_bracket_rate: Decimal
    niit: Decimal
    ohio_tax: Decimal
    total_tax: Decimal


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _load_federal_data(tax_year: int) -> dict:
    path = _DATA_DIR / f"federal_{tax_year}.json"
    if not path.exists():
        raise ValueError(f"Unsupported tax year: {tax_year}")
    with path.open() as f:
        return json.load(f)


@lru_cache(maxsize=None)
def _load_ss_data() -> dict:
    with _SS_PATH.open() as f:
        return json.load(f)


@lru_cache(maxsize=None)
def _load_ohio_data(tax_year: int) -> dict:
    path = _DATA_DIR / f"ohio_{tax_year}.json"
    if not path.exists():
        raise ValueError(f"Unsupported tax year: {tax_year}")
    with path.open() as f:
        return json.load(f)


def _get_standard_deduction(filing_status: str, tax_year: int) -> Decimal:
    return Decimal(_load_federal_data(tax_year)["standard_deduction"][filing_status])


def _get_niit_threshold(filing_status: str, tax_year: int) -> Decimal:
    return Decimal(_load_federal_data(tax_year)["niit"][filing_status])


def _get_niit_rate(tax_year: int) -> Decimal:
    return Decimal(_load_federal_data(tax_year)["niit"]["rate"])


def _get_irmaa_thresholds(filing_status: str, tax_year: int) -> list[Decimal]:
    return [Decimal(t) for t in
            _load_federal_data(tax_year)["irmaa_thresholds"][filing_status]]


def _get_default_sweep_ceiling(filing_status: str, tax_year: int) -> Decimal:
    """Return the top of the 24% ordinary bracket."""
    for bracket in _load_federal_data(tax_year)["ordinary"][filing_status]:
        if Decimal(bracket["rate"]) == Decimal("0.24"):
            return Decimal(bracket["to"])
    raise ValueError(f"No 24% bracket found for {filing_status} {tax_year}")


# ---------------------------------------------------------------------------
# Income helpers
# ---------------------------------------------------------------------------

def _compute_fixed_ordinary(
    pension: Decimal,
    interest: Decimal,
    ordinary_dividends: Decimal,
    inherited_ira_rmd: Decimal,
) -> Decimal:
    return pension + interest + ordinary_dividends + inherited_ira_rmd


def _compute_incomes_at_point(
    sweep_value: Decimal,
    sweep_mode: SweepMode,
    fixed_ordinary: Decimal,
    variable_ordinary: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (total_ordinary, total_preferential) at a sweep point."""
    if sweep_mode == SweepMode.ORDINARY:
        return fixed_ordinary + sweep_value, qualified_dividends + fixed_ltcg
    return (fixed_ordinary + variable_ordinary,
            qualified_dividends + fixed_ltcg + sweep_value)


# ---------------------------------------------------------------------------
# Social Security at a point
# ---------------------------------------------------------------------------

def _compute_ss_at_point(
    total_ordinary: Decimal,
    total_preferential: Decimal,
    tax_exempt_interest: Decimal,
    ss_benefit: Decimal,
    filing_status: str,
    above_the_line_adjustments: Decimal = _ZERO,
) -> tuple[Decimal, Decimal]:
    """Return (ss_taxable, ss_inclusion_rate)."""
    if ss_benefit == _ZERO:
        return _ZERO, _ZERO
    agi_excluding_ss = total_ordinary + total_preferential - above_the_line_adjustments
    result = calculate_social_security_taxability(
        ss_benefit=ss_benefit,
        agi_excluding_ss=agi_excluding_ss,
        tax_exempt_interest=tax_exempt_interest,
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
    above_the_line_adjustments: Decimal = _ZERO,
    additional_deductions: Decimal = _ZERO,
) -> tuple[Decimal, Decimal]:
    """Return (agi, taxable_ordinary)."""
    agi = total_ordinary + ss_taxable + total_preferential - above_the_line_adjustments
    taxable_ordinary = max(
        _ZERO,
        total_ordinary + ss_taxable - std_deduction
        - additional_deductions - above_the_line_adjustments,
    )
    return agi, taxable_ordinary


# ---------------------------------------------------------------------------
# NIIT
# ---------------------------------------------------------------------------

def _compute_niit(
    agi: Decimal,
    net_investment_income: Decimal,
    niit_threshold: Decimal,
    niit_rate: Decimal,
) -> Decimal:
    if agi > niit_threshold:
        niit_base = min(net_investment_income, agi - niit_threshold)
        return round_tax(niit_base * niit_rate)
    return _ZERO


# ---------------------------------------------------------------------------
# Ohio tax at a point
# ---------------------------------------------------------------------------

def _compute_ohio_tax_at_point(
    agi: Decimal,
    ss_taxable: Decimal,
    ohio_medical_deduction: Decimal,
    ohio_qualifying_retirement_income: Decimal,
    tax_year: int,
) -> Decimal:
    """Compute Ohio tax, reverse-engineering gross medical for fixed deduction."""
    ohio_floor_rate = Decimal(_load_ohio_data(tax_year)["medical_expense_floor_rate"])
    ohio_agi = agi - ss_taxable
    medical_floor = round_tax(ohio_agi * ohio_floor_rate)
    gross_medical = ohio_medical_deduction + medical_floor

    result = calculate_ohio_tax(
        federal_agi=agi,
        gross_medical_expenses=gross_medical,
        qualifying_retirement_income=ohio_qualifying_retirement_income,
        ss_taxable_federal=ss_taxable,
        tax_year=tax_year,
    )
    return result.ohio_tax


# ---------------------------------------------------------------------------
# Full tax snapshot at a single sweep point
# ---------------------------------------------------------------------------

def _compute_tax_snapshot(
    sweep_value: Decimal,
    sweep_mode: SweepMode,
    fixed_ordinary: Decimal,
    variable_ordinary: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    ss_benefit: Decimal,
    tax_exempt_interest: Decimal,
    std_deduction: Decimal,
    niit_threshold: Decimal,
    niit_rate: Decimal,
    filing_status: str,
    tax_year: int,
    include_ohio: bool,
    ohio_medical_deduction: Decimal,
    ohio_qualifying_retirement_income: Decimal,
    investment_ordinary: Decimal,
    above_the_line_adjustments: Decimal = _ZERO,
    additional_deductions: Decimal = _ZERO,
) -> _TaxSnapshot:
    """Compute complete tax at a single sweep point."""
    total_ordinary, total_preferential = _compute_incomes_at_point(
        sweep_value, sweep_mode, fixed_ordinary, variable_ordinary,
        qualified_dividends, fixed_ltcg,
    )

    ss_taxable, ss_inclusion_rate = _compute_ss_at_point(
        total_ordinary, total_preferential, tax_exempt_interest,
        ss_benefit, filing_status,
        above_the_line_adjustments=above_the_line_adjustments,
    )

    agi, taxable_ordinary = _compute_agi_and_taxable(
        total_ordinary, ss_taxable, total_preferential, std_deduction,
        above_the_line_adjustments=above_the_line_adjustments,
        additional_deductions=additional_deductions,
    )

    fed_result = calculate_federal_tax(
        ordinary_income=taxable_ordinary,
        preferential_income=total_preferential,
        filing_status=filing_status,
        tax_year=tax_year,
    )

    net_investment_income = investment_ordinary + total_preferential
    niit = _compute_niit(agi, net_investment_income, niit_threshold, niit_rate)

    ohio_tax = _ZERO
    if include_ohio:
        ohio_tax = _compute_ohio_tax_at_point(
            agi, ss_taxable, ohio_medical_deduction,
            ohio_qualifying_retirement_income, tax_year,
        )

    total_tax = fed_result.total_tax + niit + ohio_tax

    return _TaxSnapshot(
        total_ordinary=total_ordinary,
        total_preferential=total_preferential,
        ss_taxable=ss_taxable,
        ss_inclusion_rate=ss_inclusion_rate,
        agi=agi,
        taxable_ordinary=taxable_ordinary,
        ordinary_tax=fed_result.ordinary_income_tax,
        preferential_tax=fed_result.preferential_income_tax,
        marginal_bracket_rate=fed_result.marginal_bracket_rate,
        niit=niit,
        ohio_tax=ohio_tax,
        total_tax=total_tax,
    )


# ---------------------------------------------------------------------------
# EMR between two points
# ---------------------------------------------------------------------------

def _compute_emr_between_points(lo: _TaxSnapshot, hi: _TaxSnapshot,
                                step: Decimal) -> Decimal:
    """Return total EMR from the tax difference between two snapshots."""
    return round_rate((hi.total_tax - lo.total_tax) / step)


def _attribute_emr_components(
    lo: _TaxSnapshot,
    hi: _TaxSnapshot,
    step: Decimal,
    sweep_mode: SweepMode,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Return (emr_ordinary, emr_ss_torpedo, emr_pref_stacking, emr_niit, emr_ohio).

    emr_ordinary is the actual ordinary tax delta divided by step (ORDINARY mode) or
    zero (PREFERENTIAL mode). This is 0 below the standard deduction and equals the
    bracket rate above it, keeping emr_ordinary consistent with total emr.
    Components sum to emr within rounding tolerance.
    """
    bracket_rate = lo.marginal_bracket_rate

    if sweep_mode == SweepMode.ORDINARY:
        # Below the standard deduction both snapshots have ordinary_tax = 0; the
        # bracket rate is technically correct for the next dollar but no tax
        # actually changes, so the ordinary component must be 0.
        if hi.ordinary_tax == lo.ordinary_tax:
            emr_ordinary = _ZERO
        else:
            emr_ordinary = bracket_rate
    else:
        emr_ordinary = _ZERO

    ss_delta = (hi.ss_taxable - lo.ss_taxable) / step
    emr_ss_torpedo = round_rate(bracket_rate * ss_delta)

    emr_pref_stacking = round_rate(
        (hi.preferential_tax - lo.preferential_tax) / step)
    emr_niit = round_rate((hi.niit - lo.niit) / step)
    emr_ohio = round_rate((hi.ohio_tax - lo.ohio_tax) / step)

    return emr_ordinary, emr_ss_torpedo, emr_pref_stacking, emr_niit, emr_ohio


# ---------------------------------------------------------------------------
# Sweep array construction
# ---------------------------------------------------------------------------

def _build_regular_sweep(floor: Decimal, ceiling: Decimal,
                         step: Decimal) -> list[Decimal]:
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
) -> list[Decimal]:
    """Return Ohio-specific boundary sweep_values for zero-rate and MAGI credit thresholds.

    ohio_agi_base is total non-SS income at sweep_value=0 (ohio_agi = ohio_agi_base + sweep_value).
    Boundary points are approximate — ohio_medical_deduction is included in the zero-rate
    threshold but personal exemption is taken from the expected tier at each boundary.
    """
    ohio_data = _load_ohio_data(tax_year)
    boundaries: list[Decimal] = []

    # Zero-rate threshold: ohio_tax_base enters the first taxable bracket
    # ohio_tax_base = ohio_agi - personal_exemption - ohio_medical_deduction = brackets[1]["from"]
    # At this ohio_agi the personal_exemption is from the lowest tier (ohio_agi < $40,000)
    zero_bracket = Decimal(ohio_data["brackets"][1]["from"])          # $26,050
    exemption_low = Decimal(ohio_data["personal_exemption"][0]["amount"])  # $2,400
    ohio_agi_zero = zero_bracket + exemption_low + ohio_medical_deduction
    boundaries.append(ohio_agi_zero - ohio_agi_base)

    # MAGI credit threshold: ohio_agi - personal_exemption crosses $100,000
    # At this ohio_agi (> $80,000) the personal_exemption is the highest tier
    magi_threshold = Decimal(ohio_data["magi_credit_threshold"])      # $100,000
    exemption_high = Decimal(ohio_data["personal_exemption"][-1]["amount"])  # $1,900
    ohio_agi_magi = magi_threshold + exemption_high
    boundaries.append(ohio_agi_magi - ohio_agi_base)

    return boundaries


def _compute_ordinary_boundaries(
    fixed_ordinary: Decimal,
    total_preferential: Decimal,
    ss_benefit: Decimal,
    tax_exempt_interest: Decimal,
    std_deduction: Decimal,
    niit_threshold: Decimal,
    filing_status: str,
    tax_year: int,
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
    above_the_line_adjustments: Decimal = _ZERO,
    additional_deductions: Decimal = _ZERO,
) -> list[Decimal]:
    """Compute approximate boundary points for ORDINARY sweep mode."""
    data = _load_federal_data(tax_year)
    boundaries: list[Decimal] = []
    total_deduction = std_deduction + additional_deductions + above_the_line_adjustments

    # Standard deduction exhaustion
    boundaries.append(total_deduction - fixed_ordinary)

    # Ordinary bracket boundaries
    for bracket in data["ordinary"][filing_status]:
        if bracket["to"] is not None:
            b_to = Decimal(bracket["to"])
            boundaries.append(b_to + total_deduction - fixed_ordinary)

    # Preferential stacking boundaries
    if total_preferential > _ZERO:
        for bracket in data["preferential"][filing_status]:
            if bracket["to"] is not None:
                p_to = Decimal(bracket["to"])
                boundaries.append(
                    p_to - total_preferential + total_deduction - fixed_ordinary)
                boundaries.append(p_to + total_deduction - fixed_ordinary)

    # SS torpedo boundaries
    if ss_benefit > _ZERO:
        half_ss = ss_benefit * _HALF
        base_prov = (fixed_ordinary + total_preferential - above_the_line_adjustments
                     + tax_exempt_interest + half_ss)
        ss_data = _load_ss_data()
        tier_1 = Decimal(ss_data[filing_status]["tier_1_threshold"])
        tier_2 = Decimal(ss_data[filing_status]["tier_2_threshold"])
        boundaries.append(tier_1 - base_prov)
        boundaries.append(tier_2 - base_prov)

        tier_1_rate = Decimal(ss_data["tier_1_inclusion_rate"])
        tier_2_rate = Decimal(ss_data["tier_2_inclusion_rate"])
        max_rate = Decimal(ss_data["maximum_inclusion_rate"])
        max_tier_1 = min(tier_1_rate * ss_benefit,
                         tier_1_rate * (tier_2 - tier_1))
        max_taxable = max_rate * ss_benefit
        if max_taxable > max_tier_1:
            ss_max_prov = tier_2 + round_tax(
                (max_taxable - max_tier_1) / tier_2_rate)
            boundaries.append(ss_max_prov - base_prov)

    # NIIT threshold (approximate — ignores ss_taxable in AGI)
    boundaries.append(niit_threshold - fixed_ordinary - total_preferential)

    # Ohio discontinuity boundaries
    if include_ohio:
        ohio_agi_base = fixed_ordinary + total_preferential
        boundaries.extend(
            _compute_ohio_boundaries(ohio_agi_base, ohio_medical_deduction, tax_year))

    return boundaries


def _compute_preferential_boundaries(
    fixed_ordinary: Decimal,
    variable_ordinary: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    ss_benefit: Decimal,
    tax_exempt_interest: Decimal,
    std_deduction: Decimal,
    niit_threshold: Decimal,
    filing_status: str,
    tax_year: int,
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
    above_the_line_adjustments: Decimal = _ZERO,
    additional_deductions: Decimal = _ZERO,
) -> list[Decimal]:
    """Compute approximate boundary points for PREFERENTIAL sweep mode."""
    data = _load_federal_data(tax_year)
    boundaries: list[Decimal] = []

    total_ordinary = fixed_ordinary + variable_ordinary
    taxable_ordinary = max(
        _ZERO,
        total_ordinary - std_deduction - additional_deductions - above_the_line_adjustments,
    )
    fixed_pref = qualified_dividends + fixed_ltcg

    # Preferential bracket boundaries
    for bracket in data["preferential"][filing_status]:
        if bracket["to"] is not None:
            p_to = Decimal(bracket["to"])
            boundaries.append(p_to - taxable_ordinary - fixed_pref)

    # SS torpedo boundaries
    if ss_benefit > _ZERO:
        half_ss = ss_benefit * _HALF
        base_prov = (total_ordinary + fixed_pref - above_the_line_adjustments
                     + tax_exempt_interest + half_ss)
        ss_data = _load_ss_data()
        tier_1 = Decimal(ss_data[filing_status]["tier_1_threshold"])
        tier_2 = Decimal(ss_data[filing_status]["tier_2_threshold"])
        boundaries.append(tier_1 - base_prov)
        boundaries.append(tier_2 - base_prov)

        tier_1_rate = Decimal(ss_data["tier_1_inclusion_rate"])
        tier_2_rate = Decimal(ss_data["tier_2_inclusion_rate"])
        max_rate = Decimal(ss_data["maximum_inclusion_rate"])
        max_tier_1 = min(tier_1_rate * ss_benefit,
                         tier_1_rate * (tier_2 - tier_1))
        max_taxable = max_rate * ss_benefit
        if max_taxable > max_tier_1:
            ss_max_prov = tier_2 + round_tax(
                (max_taxable - max_tier_1) / tier_2_rate)
            boundaries.append(ss_max_prov - base_prov)

    # NIIT threshold (approximate)
    boundaries.append(niit_threshold - total_ordinary - fixed_pref)

    # Ohio discontinuity boundaries
    if include_ohio:
        ohio_agi_base = total_ordinary + fixed_pref
        boundaries.extend(
            _compute_ohio_boundaries(ohio_agi_base, ohio_medical_deduction, tax_year))

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
    pension: Decimal,
    interest: Decimal,
    ordinary_dividends: Decimal,
    inherited_ira_rmd: Decimal,
    ss_benefit: Decimal,
    qualified_dividends: Decimal,
    fixed_ltcg: Decimal,
    tax_exempt_interest: Decimal,
    sweep_mode: SweepMode,
    filing_status: str,
    tax_year: int,
    variable_ordinary: Decimal = _ZERO,
    sweep_floor: Decimal = _ZERO,
    sweep_ceiling: Decimal | None = None,
    sweep_step: Decimal = Decimal("100"),
    include_ohio: bool = False,
    ohio_medical_deduction: Decimal = _ZERO,
    ohio_qualifying_retirement_income: Decimal = _ZERO,
    above_the_line_adjustments: Decimal = _ZERO,
    additional_deductions: Decimal = _ZERO,
    extra_boundary_points: list[Decimal] | None = None,
) -> EMRResult:
    if filing_status not in ("single", "mfj"):
        raise ValueError(f"Unsupported filing status: {filing_status!r}")

    # Load data-driven defaults
    std_deduction = _get_standard_deduction(filing_status, tax_year)
    niit_threshold = _get_niit_threshold(filing_status, tax_year)
    niit_rate = _get_niit_rate(tax_year)
    irmaa_thresholds = _get_irmaa_thresholds(filing_status, tax_year)

    if sweep_ceiling is None:
        sweep_ceiling = _get_default_sweep_ceiling(filing_status, tax_year)

    fixed_ordinary = _compute_fixed_ordinary(
        pension, interest, ordinary_dividends, inherited_ira_rmd)
    investment_ordinary = interest + ordinary_dividends
    total_preferential_fixed = qualified_dividends + fixed_ltcg

    # Compute boundary points
    if sweep_mode == SweepMode.ORDINARY:
        boundaries = _compute_ordinary_boundaries(
            fixed_ordinary, total_preferential_fixed, ss_benefit,
            tax_exempt_interest, std_deduction, niit_threshold,
            filing_status, tax_year,
            include_ohio=include_ohio,
            ohio_medical_deduction=ohio_medical_deduction,
            above_the_line_adjustments=above_the_line_adjustments,
            additional_deductions=additional_deductions,
        )
    else:
        boundaries = _compute_preferential_boundaries(
            fixed_ordinary, variable_ordinary, qualified_dividends,
            fixed_ltcg, ss_benefit, tax_exempt_interest, std_deduction,
            niit_threshold, filing_status, tax_year,
            include_ohio=include_ohio,
            ohio_medical_deduction=ohio_medical_deduction,
            above_the_line_adjustments=above_the_line_adjustments,
            additional_deductions=additional_deductions,
        )

    if extra_boundary_points:
        boundaries.extend(extra_boundary_points)

    sweep_array = _build_sweep_array(
        sweep_floor, sweep_ceiling, sweep_step, boundaries)

    # Shared keyword args for _compute_tax_snapshot
    shared = dict(
        sweep_mode=sweep_mode,
        fixed_ordinary=fixed_ordinary,
        variable_ordinary=variable_ordinary,
        qualified_dividends=qualified_dividends,
        fixed_ltcg=fixed_ltcg,
        ss_benefit=ss_benefit,
        tax_exempt_interest=tax_exempt_interest,
        std_deduction=std_deduction,
        niit_threshold=niit_threshold,
        niit_rate=niit_rate,
        filing_status=filing_status,
        tax_year=tax_year,
        include_ohio=include_ohio,
        ohio_medical_deduction=ohio_medical_deduction,
        ohio_qualifying_retirement_income=ohio_qualifying_retirement_income,
        investment_ordinary=investment_ordinary,
        above_the_line_adjustments=above_the_line_adjustments,
        additional_deductions=additional_deductions,
    )

    points: list[EMRPoint] = []
    for sweep_value in sweep_array:
        lo = _compute_tax_snapshot(sweep_value, **shared)
        hi = _compute_tax_snapshot(sweep_value + _EMR_COMPUTE_STEP, **shared)

        emr = _compute_emr_between_points(lo, hi, _EMR_COMPUTE_STEP)
        (emr_ordinary, emr_ss_torpedo, emr_pref_stacking,
         emr_niit, emr_ohio) = _attribute_emr_components(
            lo, hi, _EMR_COMPUTE_STEP, sweep_mode)

        points.append(EMRPoint(
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
        ))

    return EMRResult(
        sweep_mode=sweep_mode,
        points=points,
        irmaa_thresholds=irmaa_thresholds,
        tax_year=tax_year,
        filing_status=filing_status,
    )
