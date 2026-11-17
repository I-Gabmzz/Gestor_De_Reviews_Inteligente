from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    autor: str | None = None
    contenido: str
    fecha: datetime
    fuente: str
    puntuacion: int
    estado: str
    categoria: str | None = None
    prioridad: str | None = None


class DashboardScoreCount(BaseModel):
    puntuacion: int
    total: int


class DashboardResponse(BaseModel):
    nombre_negocio: str | None = None
    total_reviews: int
    promedio_puntuacion: float | None
    reviews_nuevas: int
    reviews_en_revision: int
    reviews_atendidas: int
    reviews_urgentes: int
    distribucion_puntuaciones: list[DashboardScoreCount]
    reviews_recientes: list[DashboardReviewRead]
