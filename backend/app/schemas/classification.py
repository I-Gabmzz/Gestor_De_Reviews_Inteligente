"""Decisión interna del proveedor; null rechaza contenido no analizable."""

from app.schemas.ai import AIResponse, ReviewCategory


class ClassificationDecision(AIResponse):
    # Sin valor predeterminado: una respuesta sin el campo no es válida.
    categoria: ReviewCategory | None
