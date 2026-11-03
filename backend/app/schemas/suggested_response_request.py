"""Solicitud HU-18 controlada por servidor; no acepta datos de autoridad."""

from pydantic import BaseModel, ConfigDict


class SuggestedResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
