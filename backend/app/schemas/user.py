from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class UserList(BaseModel):
    items: list[UserRead]
    total: int
