"""Public HTTP contracts: never serialize internal provider/normalization DTOs."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.schemas.serpapi import StopReason


class ExternalReviewImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    business_data_id: str = Field(
        min_length=7, max_length=128, pattern=r"^0x[0-9a-fA-F]+:0x[0-9a-fA-F]+$",
    )


class ExternalReviewImportResponse(BaseModel):
    operation_id: str
    outcome: Literal["committed"] = "committed"
    control_status: Literal["released", "reconciliation_required"] = "released"
    source: Literal["Google"] = "Google"
    input_count: int
    inserted: int
    repeated: int
    changed: int
    omitted: int
    rejected: int
    batch_duplicates: int
    request_count: int
    incomplete: bool
    limited: bool
    stop_reason: StopReason


class ExternalReviewImportFailure(BaseModel):
    code: str
    message: str
    operation_id: str | None = None
    outcome: Literal["rejected", "rolled_back", "unknown"] = "rejected"
    committed_count: int | None = 0
    control_status: Literal["released", "reconciliation_required"] = "released"
    request_count: int = 0
    obtained: int = 0
    incomplete: bool | None = None
    limited: bool | None = None
    stop_reason: StopReason | None = None


class ExternalReviewImportErrorResponse(BaseModel):
    detail: ExternalReviewImportFailure


class ExternalReviewImportAuthErrorResponse(BaseModel):
    """Unchanged shared authentication/role error contract."""

    detail: str


class ExternalReviewImportAccessErrorResponse(RootModel[
    ExternalReviewImportErrorResponse | ExternalReviewImportAuthErrorResponse
]):
    pass


class ExternalReviewImportValidationIssue(BaseModel):
    model_config = ConfigDict(extra="allow")

    loc: list[str | int]
    msg: str
    type: str
    input: Any = None
    ctx: dict[str, Any] | None = None


class ExternalReviewImportValidationErrorResponse(BaseModel):
    detail: list[ExternalReviewImportValidationIssue]


class ExternalReviewImportUnprocessableResponse(RootModel[
    ExternalReviewImportErrorResponse | ExternalReviewImportValidationErrorResponse
]):
    """Functional 422 object or standard FastAPI request-validation error list."""
