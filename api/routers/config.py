"""Config route — returns application defaults from data/config.json."""

from fastapi import APIRouter, HTTPException

from api.models.config import ConfigResponse
from services.data_loader import load_config

router = APIRouter()


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    try:
        data = load_config()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="config.json not found")
    return ConfigResponse(**data)
