"""Minimal read-only connection discovery; approval metadata stays on the server."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExternalReviewConnectionOption(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    business_data_id: str = Field(min_length=1, max_length=128)
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal["available", "disabled"]


class ExternalReviewConnectionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["Google"] = "Google"
    import_enabled: bool
    connections: list[ExternalReviewConnectionOption]
