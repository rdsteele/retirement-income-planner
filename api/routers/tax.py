"""Tax detail route — thin wrapper around the tax_detail service."""

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
from services.federal_tax import BracketDetail
from services.ohio_tax import OhioTaxResult
from services.tax_detail import TaxDetailResult, calculate_tax_detail

logger = logging.getLogger(__name__)

router = APIRouter()

_NULL_TO = 999999999.0  # response value for the unbounded top bracket


def _d(value: float) -> Decimal:
    return Decimal(str(value))


def _to_bracket_row(row: BracketDetail) -> BracketRow:
    return BracketRow.model_validate(
        {
            "from": float(row.bracket_from),
            "to": _NULL_TO if row.bracket_to is None else float(row.bracket_to),
            "rate": float(row.rate),
            "income_taxed": float(row.income_taxed),
            "tax_amount": float(row.tax_amount),
        }
    )


def _to_ohio_detail(ohio: OhioTaxResult | None) -> OhioTaxDetail:
    if ohio is None:
        return OhioTaxDetail(included=False)
    return OhioTaxDetail(
        included=True,
        ohio_agi=float(ohio.ohio_agi),
        personal_exemption=float(ohio.personal_exemption),
        medical_deduction=float(ohio.medical_deduction),
        ohio_tax_base=float(ohio.ohio_tax_base),
        tax_before_credits=float(ohio.tax_before_credits),
        retirement_income_credit=float(ohio.retirement_income_credit),
        ohio_tax=float(ohio.ohio_tax),
        effective_rate=float(ohio.effective_rate),
    )


def _to_response(request: TaxRequest, result: TaxDetailResult) -> TaxResponse:
    income = result.income
    federal = result.federal
    return TaxResponse(
        filing_status=request.filing_status,
        tax_year=request.tax_year,
        inputs_summary=InputsSummary(
            gross_ordinary_income=float(income.gross_ordinary_income),
            ss_taxable=float(income.ss_taxable),
            above_the_line_adjustments=float(income.above_the_line_adjustments),
            agi=float(income.agi),
            standard_deduction=float(income.standard_deduction),
            additional_deductions=float(income.additional_deductions),
            taxable_ordinary=float(income.taxable_ordinary),
            taxable_preferential=float(income.taxable_preferential),
        ),
        federal=FederalTaxDetail(
            ordinary_income_tax=float(federal.ordinary_income_tax),
            preferential_income_tax=float(federal.preferential_income_tax),
            total_tax=float(federal.total_tax),
            effective_rate=float(federal.effective_rate),
            marginal_bracket_rate=float(federal.marginal_bracket_rate),
            niit=float(result.niit.niit),
            net_investment_income=float(result.niit.net_investment_income),
            bracket_breakdown=[_to_bracket_row(r) for r in result.ordinary_breakdown],
            preferential_breakdown=[_to_bracket_row(r) for r in result.preferential_breakdown],
        ),
        ohio=_to_ohio_detail(result.ohio),
        summary=TaxSummary(
            total_federal_tax=float(result.total_federal_tax),
            total_niit=float(result.total_niit),
            total_ohio_tax=float(result.total_ohio_tax),
            total_tax=float(result.total_tax),
            overall_effective_rate=float(result.overall_effective_rate),
        ),
    )


def _calculate_tax(request: TaxRequest) -> TaxResponse:
    result = calculate_tax_detail(
        income=request.to_income_inputs(),
        filing_status=request.filing_status,
        tax_year=request.tax_year,
        include_ohio=request.include_ohio,
        gross_medical_expenses=_d(request.gross_medical_expenses),
        ohio_qualifying_retirement_income=_d(request.ohio_qualifying_retirement_income),
    )
    return _to_response(request, result)


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
