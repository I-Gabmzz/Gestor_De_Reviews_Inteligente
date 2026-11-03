"""Server-only admission policy. This task never enables real acquisition."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExternalImportSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EXTERNAL_IMPORT_", env_file=None, extra="ignore", frozen=True,
        hide_input_in_errors=True,
    )

    enabled: bool = False
    page_size: int = Field(default=5, ge=1, le=20)
    max_pages: int = Field(default=1, ge=1, le=5)
    tenant_request_budget: int = Field(default=1, ge=1, le=10000)
    account_request_budget: int = Field(default=5, ge=1, le=10000)
    budget_window_seconds: int = Field(default=3600, ge=60, le=86400)
