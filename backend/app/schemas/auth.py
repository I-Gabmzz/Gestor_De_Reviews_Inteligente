"""Contratos de autenticación."""

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, model_validator


UserRole = Literal["usuario_negocio", "admin_tenant", "admin_general"]


class LoginRequest(BaseModel):
    correo: EmailStr = Field(validation_alias=AliasChoices("correo", "email"))
    password: str = Field(min_length=1)


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    correo: EmailStr
    rol: UserRole
    tenant_id: int | None

    @model_validator(mode="after")
    def validate_rol_tenant(self) -> "AuthenticatedUser":
        if self.rol == "admin_general" and self.tenant_id is not None:
            raise ValueError("admin_general no puede tener tenant_id")
        if self.rol != "admin_general" and self.tenant_id is None:
            raise ValueError("El rol requiere tenant_id")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: AuthenticatedUser
