from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserBase(BaseModel):
    tenant_id: int | None = None
    nombre: str
    correo: str
    rol: str
    estado: str


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(max_length=255)
    correo: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1)

    @field_validator("nombre")
    @classmethod
    def validate_nombre(cls, value: str) -> str:
        nombre = value.strip()
        if not nombre:
            raise ValueError("El nombre es obligatorio")
        return nombre


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, max_length=255)
    correo: EmailStr | None = Field(default=None, max_length=320)
    estado: Literal["activo", "inactivo"] | None = None

    @field_validator("nombre")
    @classmethod
    def validate_nombre(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("El nombre es obligatorio cuando se envía")
        return value.strip()

    @field_validator("correo", "estado")
    @classmethod
    def reject_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("El campo no puede ser nulo")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("Se requiere al menos un campo para actualizar")
        return self


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class UserList(BaseModel):
    items: list[UserRead]
    total: int
