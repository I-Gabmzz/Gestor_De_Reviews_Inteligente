"""Base de salidas estructuradas; cada HU define su resultado funcional."""

from pydantic import BaseModel, ConfigDict


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
