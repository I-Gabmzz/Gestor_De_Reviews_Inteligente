"""Contrato de solicitud y rechazo interno de resumen de una review."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ai import AIResponse


class SummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SummaryDecision(AIResponse):
    # null rechaza contenido no analizable y nunca se persiste como resultado.
    resumen: str | None = Field(min_length=1, max_length=400)

    @field_validator("resumen", mode="before")
    @classmethod
    def normalize_summary(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
