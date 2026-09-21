from typing import Literal

from pydantic import BaseModel, ConfigDict


class TenantBase(BaseModel):
    nombre: str
    estado: Literal["activo", "inactivo"]


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
