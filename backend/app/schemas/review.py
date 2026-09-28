from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ReviewStatus(str, Enum):
    NUEVA = "nueva"
    EN_REVISION = "en_revision"
    ATENDIDA = "atendida"


class ReviewBase(BaseModel):
    tenant_id: int
    autor: str | None = None
    contenido: str
    fecha: datetime
    fuente: str
    puntuacion: int
    estado: ReviewStatus
    categoria: str | None = None
    prioridad: str | None = None


class ReviewRead(ReviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ReviewList(BaseModel):
    items: list[ReviewRead]
    total: int


class ReviewStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: ReviewStatus
