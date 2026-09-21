from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewBase(BaseModel):
    tenant_id: int
    autor: str | None = None
    contenido: str
    fecha: datetime
    fuente: str
    puntuacion: int
    estado: str
    categoria: str | None = None
    prioridad: str | None = None


class ReviewRead(ReviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ReviewList(BaseModel):
    items: list[ReviewRead]
    total: int
