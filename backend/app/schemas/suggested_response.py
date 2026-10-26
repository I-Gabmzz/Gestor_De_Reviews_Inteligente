"""Contrato de HU-18; todavía no forma parte de la persistencia común."""

from pydantic import Field, field_validator

from app.schemas.ai import AIResponse


class SuggestedResponseDecision(AIResponse):
    """null es rechazo interno del contenido, nunca un resultado exitoso."""

    respuesta_sugerida: str | None = Field(min_length=1)

    @field_validator("respuesta_sugerida", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SuggestedResponseResult(SuggestedResponseDecision):
    """Solo el texto validado puede devolverse como sugerencia válida."""

    respuesta_sugerida: str = Field(min_length=1)
