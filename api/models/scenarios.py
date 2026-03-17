"""Pydantic models for the scenarios route."""

from pydantic import BaseModel


class ScenarioMetaResponse(BaseModel):
    name: str
    saved_at: str


class CurrentScenarioResponse(BaseModel):
    name: str | None


class CurrentScenarioRequest(BaseModel):
    name: str | None
