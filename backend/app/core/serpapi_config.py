"""Configuración diferida: importar el módulo no carga credenciales."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SerpApiSettings(BaseSettings):
    serpapi_api_key: SecretStr = Field(repr=False, exclude=True)
    serpapi_page_size: int = Field(default=5, ge=1, le=20)
    serpapi_max_pages: int = Field(default=3, ge=1, le=5)
    serpapi_sort_by: Literal["qualityScore", "newestFirst", "ratingHigh", "ratingLow"] = "newestFirst"
    serpapi_timeout_seconds: float = Field(default=30, gt=0, le=120, allow_inf_nan=False)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        frozen=True,
    )

    @field_validator("serpapi_api_key")
    @classmethod
    def require_api_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()
        if not key or any(ord(char) < 33 or ord(char) > 126 for char in key):
            raise ValueError("La credencial de SerpApi está ausente o no es válida")
        return SecretStr(key)
