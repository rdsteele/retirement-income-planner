"""Pydantic model for the tax-years route."""

from pydantic import BaseModel


class TaxYearsResponse(BaseModel):
    years: list[int]
    default_year: int
