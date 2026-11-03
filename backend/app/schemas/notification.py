"""Lectura paginada de avisos vigentes; no admite creación desde el cliente."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_validator


class NotificationRead(BaseModel):
    id: int
    review_id: int
    creada_en: datetime
    autor: str | None
    extracto: str
    prioridad: Literal["Alta"] = "Alta"

    @field_validator("creada_en")
    @classmethod
    def expose_utc(cls, value: datetime) -> datetime:
        # SQLite conserva el valor UTC pero no la información de zona horaria.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class NotificationList(BaseModel):
    items: list[NotificationRead]
    total: int
