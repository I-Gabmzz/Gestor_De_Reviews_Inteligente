from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    tenant_id: int | None = None
    nombre: str
    correo: str
    rol: str
    estado: str


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
