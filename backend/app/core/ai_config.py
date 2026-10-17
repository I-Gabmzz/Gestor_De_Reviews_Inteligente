"""Configuración de IA cargada al solicitar el adaptador, no al iniciar FastAPI."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    ai_provider: Literal["gemini"] = "gemini"
    ai_model: str = Field(
        default="gemini-3.5-flash-lite",
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9.-]*$",
    )
    gemini_api_key: SecretStr = Field(repr=False)
    ai_timeout_seconds: float = Field(default=30, gt=0, le=120, allow_inf_nan=False)
    ai_max_output_tokens: int = Field(default=1024, ge=64, le=8192)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("gemini_api_key")
    @classmethod
    def require_api_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()
        if not key or any(ord(char) < 33 or ord(char) > 126 for char in key):
            raise ValueError("La credencial de IA está ausente o no es válida")
        return SecretStr(key)
