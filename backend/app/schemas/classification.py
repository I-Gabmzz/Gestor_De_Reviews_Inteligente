"""Solicitud HTTP sin campos y decisión interna de clasificación."""

from app.schemas.ai import AIResponse, ReviewCategory
from pydantic import BaseModel, ConfigDict


class ClassificationRequest(BaseModel):
    """La operación usa la review del servidor, sin parámetros editables."""

    model_config = ConfigDict(extra="forbid")


class ClassificationDecision(AIResponse):
    # Sin valor predeterminado: una respuesta sin el campo no es válida.
    categoria: ReviewCategory | None
