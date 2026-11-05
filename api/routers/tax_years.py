"""Tax years route — lists years that have federal, Ohio and ACA data files."""

import re
from pathlib import Path

from fastapi import APIRouter

from api.models.tax_years import TaxYearsResponse

router = APIRouter()

_BRACKETS_DIR = Path(__file__).parent.parent.parent / "data" / "brackets"
_ACA_DIR = Path(__file__).parent.parent.parent / "data" / "aca"
_FEDERAL_PATTERN = re.compile(r"^federal_(\d{4})\.json$")


def _has_all_data_files(year: int) -> bool:
    return (_BRACKETS_DIR / f"ohio_{year}.json").exists() and (
        _ACA_DIR / f"aca_{year}.json"
    ).exists()


def _scan_years() -> list[int]:
    years = [
        int(m.group(1))
        for path in _BRACKETS_DIR.iterdir()
        if (m := _FEDERAL_PATTERN.match(path.name))
    ]
    return sorted(year for year in years if _has_all_data_files(year))


@router.get("/tax-years", response_model=TaxYearsResponse)
def get_tax_years() -> TaxYearsResponse:
    years = _scan_years()
    return TaxYearsResponse(years=years, default_year=max(years))
