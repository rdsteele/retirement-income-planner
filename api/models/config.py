"""Pydantic model for the config route."""

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    irmaa_inflation_default: float
    y_axis_max_emr: float
    sweep_step_default: float
