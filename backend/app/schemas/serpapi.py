"""Contratos internos en memoria; no son esquemas de endpoints ni modelos ORM.

Los campos nativos pueden contener datos personales. Se excluyen de repr, pero
siguen siendo sensibles al acceder explícitamente a ellos o serializarlos.
"""

from dataclasses import dataclass, field
from typing import Any, Literal


StopReason = Literal["no_next_token", "empty_with_token", "repeated_token", "max_pages", "error"]


@dataclass(frozen=True, slots=True)
class SerpApiReview:
    data: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class SerpApiPage:
    number: int
    http_status: int
    search_status: Literal["Success"]
    reviews: tuple[SerpApiReview, ...] = field(repr=False)
    next_page_token: str | None = field(default=None, repr=False)
    # Provenance of THIS page, never filled from the requested establishment.
    place_data_id: str | None = field(default=None, repr=False)
    provenance_verified: bool = False


@dataclass(frozen=True, slots=True)
class SerpApiResult:
    pages: tuple[SerpApiPage, ...] = field(repr=False)
    place_info: dict[str, Any] | None = field(repr=False)
    first_page_metadata: dict[str, Any] | None = field(repr=False)
    request_count: int
    record_count: int
    stop_reason: StopReason
    incomplete: bool
    limited: bool

    @property
    def reviews(self) -> tuple[SerpApiReview, ...]:
        return tuple(review for page in self.pages for review in page.reviews)
