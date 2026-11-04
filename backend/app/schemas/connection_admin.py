"""Contratos del panel de administración; las credenciales nunca se devuelven."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr
from app.schemas.tenant import TenantRead
from app.schemas.user import UserRead


class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class GoogleConnectionInput(AdminInput):
    tenant_id: int = Field(gt=0)
    google_maps_url: str = Field(min_length=1, max_length=4096)
    confirmed: bool


class GoogleConnectionStateInput(AdminInput):
    tenant_id: int = Field(gt=0)
    business_data_id: str = Field(max_length=128, pattern=r"^0x[0-9a-fA-F]+:0x[0-9a-fA-F]+$")
    enabled: bool


class AdminAccountInput(AdminInput):
    tenant_id: int | None = Field(default=None, gt=0)
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    nombre: str = Field(min_length=1, max_length=255)
    correo: EmailStr
    password: SecretStr = Field(repr=False, exclude=True)
    rol: Literal["admin_tenant", "usuario_negocio"] = "admin_tenant"
    google_maps_url: str | None = Field(default=None, max_length=4096)
    confirmed: bool = False


class AdminConnectionRead(BaseModel):
    business_data_id: str
    enabled: bool
    google_maps_url: str


class AdminConnectionList(BaseModel):
    tenant: TenantRead
    connections: list[AdminConnectionRead]
    users: list[UserRead] = Field(default_factory=list)


class AdminAccountRead(BaseModel):
    tenant: TenantRead
    user: UserRead
    connection: AdminConnectionRead | None = None
