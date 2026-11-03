"""Resultado interno de #3834; sólo contadores y diagnósticos sanitizados."""

from dataclasses import dataclass

from app.schemas.external_review import NormalizationIssue, RecordPosition
from app.schemas.serpapi import StopReason


@dataclass(frozen=True, slots=True)
class ExternalReviewPersistenceResult:
    input_count: int
    inserted: int
    repeated: int
    changed: int
    omitted: int
    rejected: int
    batch_duplicates: int
    incomplete: bool
    limited: bool
    stop_reason: StopReason
    changed_positions: tuple[RecordPosition, ...] = ()
    warnings: tuple[NormalizationIssue, ...] = ()
