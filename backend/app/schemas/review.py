from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ReviewManualCreate(BaseModel):
    """Datos que un usuario puede capturar para una review manual."""

    model_config = ConfigDict(extra="forbid")

    autor: str | None = None
    contenido: str
    fecha: datetime
    puntuacion: int = Field(ge=1, le=5)

    @field_validator("autor")
    @classmethod
    def normalize_autor(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("contenido")
    @classmethod
    def validate_contenido(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("El contenido no puede estar vacío")
        return normalized_value


class ReviewManualRegistration(ReviewManualCreate):
    """Datos internos listos para que T3 persista una review manual."""

    tenant_id: int
    fuente: Literal["manual"] = "manual"
    estado: Literal["nueva"] = "nueva"
    categoria: None = None
    prioridad: None = None


class ReviewRead(ReviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ReviewList(BaseModel):
    items: list[ReviewRead]
    total: int
