"""Decisión interna de HU-15, independiente del contrato persistible común."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.ai import AIResponse


ReviewTopic = Literal["Atención", "Servicio", "Precio", "Producto", "Otro"]


class TopicDecision(AIResponse):
    # null expresa rechazo interno; nunca debe persistirse como TopicResult.
    tema: ReviewTopic | None


class TopicRequest(BaseModel):
    """La operación usa exclusivamente el contenido guardado en el servidor."""

    model_config = ConfigDict(extra="forbid")
