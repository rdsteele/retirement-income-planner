"""Tax detail route — point-in-time federal and Ohio tax calculation."""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from api.models.tax import (
    BracketRow,
    FederalTaxDetail,
    InputsSummary,
    OhioTaxDetail,
    TaxRequest,
    TaxResponse,
    TaxSummary,
)
from services.common import round_rate, round_tax
from services.data_loader import load_federal_data
from services.federal_tax import calculate_federal_tax
from services.ohio_tax import calculate_ohio_tax
from services.social_security import calculate_social_security_taxability

logger = logging.getLogger(__name__)

router = APIRouter()

_D = Decimal
_ZERO = _D("0")
_NULL_TO = 999999999.0


def _d(value: float) -> Decimal:
    return _D(str(value))


def _bracket_row(bracket: dict, income_taxed: Decimal, tax_amount: Decimal) -> BracketRow:
    return BracketRow.model_validate(
        {
            "from": float(_D(bracket["from"])),
            "to": _NULL_TO if bracket["to"] is None else float(_D(bracket["to"])),
            "rate": float(_D(bracket["rate"])),
            "income_taxed": float(income_taxed),
            "tax_amount": float(tax_amount),
        }
    )


def _build_ordinary_breakdown(taxable_ordinary: Decimal, brackets: list[dict]) -> list[BracketRow]:
    rows: list[BracketRow] = []
    residual = taxable_ordinary
    for bracket in brackets:
        if bracket["to"] is not None:
            bracket_range = _D(bracket["to"]) - _D(bracket["from"])
            income_taxed = min(residual, bracket_range)
        else:
            income_taxed = residual
        residual -= income_taxed
        tax_amount = round_tax(income_taxed * _D(bracket["rate"]))
        if income_taxed > _ZERO:
            rows.append(_bracket_row(bracket, income_taxed, tax_amount))
        if residual <= _ZERO:
            break
    if not rows:
        rows.append(_bracket_row(brackets[0], _ZERO, _ZERO))
    return rows


def _build_pref_breakdown(
    taxable_ordinary: Decimal,
    total_preferential: Decimal,
    brackets: list[dict],
) -> list[BracketRow]:
    rows: list[BracketRow] = []
    remaining_pref = total_preferential
    stack_base = taxable_ordinary
    for bracket in brackets:
        b_from_dec = _D(bracket["from"])
        bracket_start = max(stack_base, b_from_dec)
        if bracket["to"] is not None:
            b_to_dec = _D(bracket["to"])
            if bracket_start >= b_to_dec:
                continue  # ordinary income fills this entire bracket
            available = b_to_dec - bracket_start
        else:
            available = remaining_pref
        income_taxed = min(remaining_pref, available)
        remaining_pref -= income_taxed
        tax_amount = round_tax(income_taxed * _D(bracket["rate"]))
        if income_taxed > _ZERO:
            rows.append(_bracket_row(bracket, income_taxed, tax_amount))
        if remaining_pref <= _ZERO:
            break
    if not rows:
        rows.append(_bracket_row(brackets[0], _ZERO, _ZERO))
    return rows


@router.post("/tax", response_model=TaxResponse)
def post_tax(request: TaxRequest):
    try:
        return _calculate_tax(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error in tax calculation")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        )


def _calculate_tax(request: TaxRequest) -> TaxResponse:
    pension = _d(request.pension)
    interest = _d(request.interest)
    ordinary_dividends = _d(request.ordinary_dividends)
    qualified_dividends = _d(request.qualified_dividends)
    ira_distributions = _d(request.ira_distributions)
    ss_benefit = _d(request.ss_benefit)
    fixed_ltcg = _d(request.fixed_ltcg)
    tax_exempt_interest = _d(request.tax_exempt_interest)
    wages = _d(request.wages)
    above_the_line = _d(request.above_the_line_adjustments)
    additional_deductions = _d(request.additional_deductions)
    filing_status = request.filing_status
    tax_year = request.tax_year

    # Step 1 — SS taxability
    gross_ordinary = pension + interest + ordinary_dividends + ira_distributions + wages
    total_preferential = qualified_dividends + fixed_ltcg
    agi_excluding_ss = gross_ordinary + total_preferential - above_the_line
    ss_result = calculate_social_security_taxability(
        ss_benefit=ss_benefit,
        agi_excluding_ss=agi_excluding_ss,
        tax_exempt_interest=tax_exempt_interest,
        filing_status=filing_status,
    )
    ss_taxable = ss_result.taxable_ss

    # Step 2 — Federal tax
    data = load_federal_data(tax_year)
    standard_deduction = _D(data["standard_deduction"][filing_status])
    total_ordinary = gross_ordinary + ss_taxable - above_the_line
    taxable_ordinary = max(_ZERO, total_ordinary - standard_deduction - additional_deductions)
    federal_result = calculate_federal_tax(
        ordinary_income=taxable_ordinary,
        preferential_income=total_preferential,
        filing_status=filing_status,
        tax_year=tax_year,
    )

    # Step 3 — Ohio tax (optional)
    federal_agi = total_ordinary + total_preferential
    if request.include_ohio:
        ohio_result = calculate_ohio_tax(
            federal_agi=federal_agi,
            gross_medical_expenses=_d(request.gross_medical_expenses),
            qualifying_retirement_income=_d(request.ohio_qualifying_retirement_income),
            ss_taxable_federal=ss_taxable,
            tax_year=tax_year,
        )
        ohio_detail = OhioTaxDetail(
            included=True,
            ohio_agi=float(ohio_result.ohio_agi),
            personal_exemption=float(ohio_result.personal_exemption),
            medical_deduction=float(ohio_result.medical_deduction),
            ohio_tax_base=float(ohio_result.ohio_tax_base),
            tax_before_credits=float(ohio_result.tax_before_credits),
            retirement_income_credit=float(ohio_result.retirement_income_credit),
            ohio_tax=float(ohio_result.ohio_tax),
            effective_rate=float(ohio_result.effective_rate),
        )
        total_ohio_tax = float(ohio_result.ohio_tax)
    else:
        ohio_detail = OhioTaxDetail(included=False)
        total_ohio_tax = 0.0

    # Build bracket breakdowns
    ordinary_brackets = data["ordinary"][filing_status]
    pref_brackets = data["preferential"][filing_status]
    bracket_breakdown = _build_ordinary_breakdown(taxable_ordinary, ordinary_brackets)
    pref_breakdown = _build_pref_breakdown(taxable_ordinary, total_preferential, pref_brackets)

    # inputs_summary
    agi = float(federal_agi)
    inputs_summary = InputsSummary(
        gross_ordinary_income=float(gross_ordinary),
        ss_taxable=float(ss_taxable),
        above_the_line_adjustments=float(above_the_line),
        agi=agi,
        standard_deduction=float(standard_deduction),
        additional_deductions=float(additional_deductions),
        taxable_ordinary=float(taxable_ordinary),
        taxable_preferential=float(total_preferential),
    )

    # Federal detail
    federal_detail = FederalTaxDetail(
        ordinary_income_tax=float(federal_result.ordinary_income_tax),
        preferential_income_tax=float(federal_result.preferential_income_tax),
        total_tax=float(federal_result.total_tax),
        effective_rate=float(federal_result.effective_rate),
        marginal_bracket_rate=float(federal_result.marginal_bracket_rate),
        bracket_breakdown=bracket_breakdown,
        preferential_breakdown=pref_breakdown,
    )

    # Summary
    total_federal_tax = float(federal_result.total_tax)
    total_tax = total_federal_tax + total_ohio_tax
    agi_dec = federal_agi
    overall_rate = float(round_rate(_D(str(total_tax)) / agi_dec)) if agi_dec > _ZERO else 0.0

    summary = TaxSummary(
        total_federal_tax=total_federal_tax,
        total_ohio_tax=total_ohio_tax,
        total_tax=total_tax,
        overall_effective_rate=overall_rate,
    )

    return TaxResponse(
        filing_status=filing_status,
        tax_year=tax_year,
        inputs_summary=inputs_summary,
        federal=federal_detail,
        ohio=ohio_detail,
        summary=summary,
    )
