from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ReviewUpdate(BaseModel):
    """Campos autorizados para la edición parcial de una review."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    autor: str | None = Field(default=None, max_length=255)
    contenido: str | None = Field(default=None, min_length=1)
    fecha: datetime | None = None
    fuente: str | None = Field(default=None, min_length=1, max_length=100)
    puntuacion: int | None = Field(default=None, ge=1, le=5, strict=True)

    @field_validator("autor")
    @classmethod
    def normalize_author(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("fecha", mode="before")
    @classmethod
    def parse_iso_date(cls, value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.strip())
            except ValueError as error:
                raise ValueError("La fecha debe ser válida y usar formato ISO 8601") from error
        raise ValueError("La fecha debe ser válida y usar formato ISO 8601")

    @field_validator("fecha")
    @classmethod
    def normalize_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @field_validator("contenido", "fuente", "puntuacion")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("El campo no puede ser null")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Debe proporcionar al menos un campo editable")
        return self


class ReviewList(BaseModel):
    items: list[ReviewRead]
    total: int


class ReviewStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: ReviewStatus
