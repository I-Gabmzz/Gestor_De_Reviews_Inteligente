"""Decisión interna y resultado válido de priorización de HU-16."""

from pydantic import BaseModel, ConfigDict

from app.schemas.ai import AIResponse, ReviewPriority
from app.schemas.ai import PriorityResult as PriorityResult


class PriorityDecision(AIResponse):
    # Campo obligatorio; null rechaza contenido no analizable, nunca se guarda.
    prioridad: ReviewPriority | None


class PriorityRequest(BaseModel):
    """La generación usa el contenido y el tenant resueltos en el servidor."""

    model_config = ConfigDict(extra="forbid")
