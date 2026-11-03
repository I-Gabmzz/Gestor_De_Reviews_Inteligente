"""Contratos internos en memoria de #3833; no son modelos ORM ni de API pública.

El normalizador es la frontera de validación. Los DTO no serializan ni registran
datos. Sus atributos siguen siendo sensibles aunque se oculten en ``repr``.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.schemas.serpapi import StopReason


IssueCode = Literal[
    "required", "invalid_type", "invalid_unicode", "too_long", "invalid_date",
    "timezone_required", "invalid_rating", "unsupported_source", "invalid_record",
    "conflicting_duplicate", "missing_author", "missing_content",
    "invalid_business_context", "invalid_result",
]
ContentField = Literal["extracted_snippet.original", "snippet"]


@dataclass(frozen=True, slots=True)
class RecordPosition:
    """Página del cliente, índice en página y ordinal del lote, todos desde 1."""

    page: int
    index: int
    ordinal: int


@dataclass(frozen=True, slots=True)
class NormalizationIssue:
    position: RecordPosition | None
    field: str
    code: IssueCode


@dataclass(frozen=True, slots=True)
class NormalizedExternalReview:
    position: RecordPosition = field(compare=False)
    external_review_id: str = field(repr=False)
    source: Literal["Google"] = field(repr=False)
    author: str | None = field(repr=False)
    content: str | None = field(repr=False)
    review_date: datetime = field(repr=False)
    rating: int = field(repr=False)
    business_data_id: str = field(repr=False)
    content_field: ContentField | None = field(repr=False)

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.source, self.business_data_id, self.external_review_id


@dataclass(frozen=True, slots=True)
class RejectedReview:
    position: RecordPosition
    issues: tuple[NormalizationIssue, ...]


@dataclass(frozen=True, slots=True)
class DuplicateReview:
    position: RecordPosition
    kept_position: RecordPosition


@dataclass(frozen=True, slots=True)
class ConflictingReviews:
    """Versiones normalizadas sensibles, exclusivamente para revisión en memoria."""

    records: tuple[NormalizedExternalReview, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class NormalizationCounts:
    total: int
    with_text: int
    without_text: int
    rejected: int
    duplicates: int
    conflicting: int  # Subconjunto de rejected; no se suma de nuevo a total.


@dataclass(frozen=True, slots=True)
class NormalizationBatchResult:
    input_count: int = 0
    with_text: tuple[NormalizedExternalReview, ...] = field(default=(), repr=False)
    without_text: tuple[NormalizedExternalReview, ...] = field(default=(), repr=False)
    rejected: tuple[RejectedReview, ...] = ()
    duplicates: tuple[DuplicateReview, ...] = ()
    conflicts: tuple[ConflictingReviews, ...] = field(default=(), repr=False)
    warnings: tuple[NormalizationIssue, ...] = ()
    batch_error: NormalizationIssue | None = None
    incomplete: bool = True
    limited: bool = False
    stop_reason: StopReason | None = None

    @property
    def counts(self) -> NormalizationCounts:
        return NormalizationCounts(
            total=self.input_count, with_text=len(self.with_text),
            without_text=len(self.without_text), rejected=len(self.rejected),
            duplicates=len(self.duplicates),
            conflicting=sum(len(group.records) for group in self.conflicts),
        )
