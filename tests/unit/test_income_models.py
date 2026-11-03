"""Tests for the shared income request model and the field-set consistency between
the layers (so adding an income field cannot be forgotten in one place)."""

import dataclasses
from decimal import Decimal

import pytest
from pydantic import ValidationError

from api.models.emr import EMRRequest
from api.models.income import IncomeInputsRequest
from api.models.income_plan import IncomePlanRequest
from api.models.scenarios import ScenarioSweepInputsResponse
from api.models.tax import TaxRequest
from api.models.total_cost import TotalCostRequest
from services.income_inputs import IncomeInputs

_INCOME_FIELDS = {f.name for f in dataclasses.fields(IncomeInputs)}


class TestFieldSetsStayInSync:
    def test_request_base_has_exactly_the_income_fields(self):
        assert set(IncomeInputsRequest.model_fields) == _INCOME_FIELDS

    def test_scenario_sweep_inputs_response_has_exactly_the_income_fields(self):
        assert set(ScenarioSweepInputsResponse.model_fields) == _INCOME_FIELDS

    @pytest.mark.parametrize("model", [EMRRequest, TotalCostRequest, TaxRequest, IncomePlanRequest])
    def test_every_request_model_accepts_every_income_field(self, model):
        assert _INCOME_FIELDS <= set(model.model_fields)

    @pytest.mark.parametrize("model", [EMRRequest, TotalCostRequest, TaxRequest, IncomePlanRequest])
    def test_every_request_model_builds_on_the_shared_base(self, model):
        assert issubclass(model, IncomeInputsRequest)


class TestToIncomeInputs:
    def test_defaults_are_zero(self):
        assert IncomeInputsRequest().to_income_inputs() == IncomeInputs()

    def test_converts_floats_to_exact_decimals(self):
        request = IncomeInputsRequest(pension=1600.0, interest=0.1, wages=5000.0)
        income = request.to_income_inputs()
        assert (income.pension, income.interest, income.wages) == (
            Decimal("1600.0"),
            Decimal("0.1"),
            Decimal("5000.0"),
        )

    def test_every_field_is_carried_across(self):
        values = {name: float(i + 1) for i, name in enumerate(sorted(_INCOME_FIELDS))}
        income = IncomeInputsRequest(**values).to_income_inputs()
        assert {n: float(getattr(income, n)) for n in _INCOME_FIELDS} == values

    def test_negative_amounts_are_rejected(self):
        with pytest.raises(ValidationError):
            IncomeInputsRequest(interest=-1.0)

    def test_emr_request_uses_the_shared_conversion(self):
        request = EMRRequest(
            sweep_mode="ordinary", filing_status="single", tax_year=2026, ira_distributions=5.0
        )
        assert request.to_income_inputs().ira_distributions == Decimal("5.0")

    def test_tax_request_carries_wages(self):
        request = TaxRequest(filing_status="single", tax_year=2026, wages=1234.0)
        assert request.to_income_inputs().wages == Decimal("1234.0")


class TestIncomePlanRequest:
    def _request(self, **kwargs):
        return IncomePlanRequest(filing_status="single", tax_year=2026, **kwargs)

    def test_the_taxable_pension_is_what_flows_into_income(self):
        income = self._request(pension=6000.0, pension_taxable=1600.0).to_income_inputs()
        assert income.pension == Decimal("1600.0")

    def test_the_gross_pension_stays_available_for_cash_flow(self):
        assert self._request(pension=6000.0, pension_taxable=1600.0).pension == 6000.0

    def test_other_fields_pass_through(self):
        income = self._request(interest=40.0, other_investment_ordinary=300.0).to_income_inputs()
        assert (income.interest, income.other_investment_ordinary) == (
            Decimal("40.0"),
            Decimal("300.0"),
        )
