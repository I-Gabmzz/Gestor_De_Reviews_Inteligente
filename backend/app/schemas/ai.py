"""Salidas comunes de IA; las reglas semánticas corresponden a cada HU."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


ReviewCategory = Literal["Queja", "Sugerencia", "Felicitación", "Consulta"]


class ClassificationResult(AIResponse):
    categoria: ReviewCategory


class SummaryResult(AIResponse):
    resumen: str = Field(min_length=1, max_length=400)

    @field_validator("resumen", mode="before")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("El resumen no puede estar vacío")
        return value.strip()


class TopicResult(AIResponse):
    tema: str = Field(min_length=1)

    @field_validator("tema")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El tema no puede estar vacío")
        return value


AIResult = ClassificationResult | SummaryResult | TopicResult
