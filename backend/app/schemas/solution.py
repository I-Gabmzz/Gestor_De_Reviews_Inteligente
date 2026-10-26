"""Contrato de solicitud y rechazo interno de solución de una review."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ai import AIResponse


class SolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SolutionDecision(AIResponse):
    # null rechaza contenido no analizable y nunca se persiste como resultado.
    solucion: str | None = Field(min_length=1, max_length=1000)

    @field_validator("solucion", mode="before")
    @classmethod
    def normalize_summary(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
