from pydantic import BaseModel, ConfigDict


class TenantBase(BaseModel):
    nombre: str
    estado: str


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
