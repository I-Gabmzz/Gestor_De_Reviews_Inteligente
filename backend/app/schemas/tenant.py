from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

TenantEstado = Literal["activo", "inactivo"]
TenantName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class TenantBase(BaseModel):
    nombre: str
    estado: TenantEstado


class TenantCreate(TenantBase):
    model_config = ConfigDict(extra="forbid")

    nombre: TenantName
    estado: TenantEstado = "activo"


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: TenantName | None = None
    estado: TenantEstado | None = None

    @field_validator("nombre", "estado")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("El campo no puede ser null")
        return value


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TenantList(BaseModel):
    items: list[TenantRead]
    total: int
