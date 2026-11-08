"""Config route — returns application defaults from data/config.json."""

from fastapi import APIRouter, HTTPException

from api.models.config import ConfigResponse
from services.data_loader import load_config
from services.senior_deduction import senior_deduction_years

router = APIRouter()


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    try:
        data = load_config()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="config.json not found")
    first_year, last_year = senior_deduction_years()
    return ConfigResponse(
        **data, senior_deduction_years={"first_year": first_year, "last_year": last_year}
    )
