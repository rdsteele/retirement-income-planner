"""Config route — reads data/config.json and returns application defaults."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models.config import ConfigResponse

router = APIRouter()

_CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "config.json"


def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        raise HTTPException(status_code=500, detail="config.json not found")
    return json.loads(_CONFIG_PATH.read_text())


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    data = _load_config()
    return ConfigResponse(**data)
