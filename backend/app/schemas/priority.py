"""Decisión interna y resultado válido de priorización de HU-16."""

from typing import Literal

from app.schemas.ai import AIResponse


ReviewPriority = Literal["Baja", "Media", "Alta"]


class PriorityResult(AIResponse):
    prioridad: ReviewPriority


class PriorityDecision(AIResponse):
    # Campo obligatorio; null rechaza contenido no analizable, nunca se guarda.
    prioridad: ReviewPriority | None
