"""Scenarios API router.

Route order matters: /scenarios/current must be registered before
/scenarios/{name} to prevent FastAPI treating "current" as a name param.
"""

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Response
from fastapi.responses import JSONResponse

import services.scenarios as svc
from api.models.scenarios import (
    CurrentScenarioRequest,
    CurrentScenarioResponse,
    ScenarioMetaResponse,
)

router = APIRouter()


@router.get("/scenarios", response_model=list[ScenarioMetaResponse])
def get_scenarios() -> list[ScenarioMetaResponse]:
    try:
        metas = svc.list_scenarios()
        return [
            ScenarioMetaResponse(name=m.name, saved_at=m.saved_at.isoformat())
            for m in metas
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# /current routes MUST be defined before /{name}

@router.get("/scenarios/current", response_model=CurrentScenarioResponse)
def get_current_scenario() -> CurrentScenarioResponse:
    try:
        name = svc.get_current_scenario()
        return CurrentScenarioResponse(name=name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/scenarios/current", response_model=CurrentScenarioResponse)
def set_current_scenario(request: CurrentScenarioRequest) -> CurrentScenarioResponse:
    try:
        svc.set_current_scenario(request.name)
        return CurrentScenarioResponse(name=request.name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/scenarios/{name}")
def get_scenario(name: str) -> JSONResponse:
    try:
        data = svc.load_scenario(name)
        return JSONResponse(content=data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/scenarios/{name}")
def post_scenario(
    name: str,
    data: dict[str, Any] = Body(...),
) -> dict[str, str]:
    try:
        svc.save_scenario(name, data)
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/scenarios/{name}", status_code=204)
def delete_scenario(name: str) -> Response:
    try:
        svc.delete_scenario(name)
        return Response(status_code=204)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
