"""Normalización pura de reseñas Google recibidas por SerpApi, sin efectos de E/S."""

from datetime import datetime, timezone
import math
import re

from app.schemas.external_review import (
    ConflictingReviews, ContentField, DuplicateReview, IssueCode,
    NormalizationBatchResult, NormalizationIssue, NormalizedExternalReview,
    RecordPosition, RejectedReview,
)
from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview


_BUSINESS_ID = re.compile(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+")
_ISO_DATE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)
_STOP_REASONS = ("no_next_token", "empty_with_token", "repeated_token", "max_pages", "error")


class _InvalidField(Exception):
    """Sólo claves de diagnóstico internas; nunca recibe el valor del proveedor."""

    def __init__(self, field: str, code: IssueCode) -> None:
        self.field = field
        self.code = code
        super().__init__(field, code)


def _text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise _InvalidField(field, "invalid_type")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _InvalidField(field, "invalid_unicode") from None
    return value.strip() or None


def _identifier(value: object) -> str:
    if _text(value, "review_id") is None:
        raise _InvalidField("review_id", "required")
    # La comprobación de vacío no altera el identificador opaco.
    return value


def _author(data: dict) -> str | None:
    user = data.get("user")
    if user is None:
        return None
    if type(user) is not dict:
        raise _InvalidField("user.name", "invalid_type")
    author = _text(user.get("name"), "user.name")
    if author is not None and len(author) > 255:
        raise _InvalidField("user.name", "too_long")
    return author


def _content(data: dict) -> tuple[str | None, ContentField | None]:
    extracted = data.get("extracted_snippet")
    if extracted is not None and type(extracted) is not dict:
        raise _InvalidField("extracted_snippet.original", "invalid_type")
    original = _text(extracted.get("original"), "extracted_snippet.original") if extracted is not None else None
    # Validar también la alternativa presente: no ocultar un tipo malformado.
    snippet = _text(data.get("snippet"), "snippet")
    if original is not None:
        return original, "extracted_snippet.original"
    if snippet is not None:
        return snippet, "snippet"
    return None, None


def _date(value: object) -> datetime:
    text = _text(value, "iso_date")
    if text is None:
        raise _InvalidField("iso_date", "required")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise _InvalidField("iso_date", "invalid_date") from None
    if parsed.tzinfo is None:
        raise _InvalidField("iso_date", "timezone_required")
    # Subconjunto ISO inequívoco, sin pérdida de precisión ni offset desconocido.
    if _ISO_DATE.fullmatch(text) is None or text.endswith("-00:00"):
        raise _InvalidField("iso_date", "invalid_date")
    try:
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise _InvalidField("iso_date", "invalid_date") from None


def _rating(value: object) -> int:
    if type(value) not in (int, float):
        raise _InvalidField("rating", "invalid_rating")
    if type(value) is float and (not math.isfinite(value) or not value.is_integer()):
        raise _InvalidField("rating", "invalid_rating")
    if not 1 <= value <= 5:
        raise _InvalidField("rating", "invalid_rating")
    return int(value)


def _record(data: dict, position: RecordPosition, business_data_id: str) -> NormalizedExternalReview:
    external_id = _identifier(data.get("review_id"))
    if type(data.get("source")) is not str or data["source"] != "Google":
        raise _InvalidField("source", "unsupported_source")
    author = _author(data)
    content, content_field = _content(data)
    return NormalizedExternalReview(
        position=position, external_review_id=external_id, source="Google",
        author=author, content=content, review_date=_date(data.get("iso_date")),
        rating=_rating(data.get("rating")), business_data_id=business_data_id,
        content_field=content_field,
    )


def _valid_envelope(result: object) -> bool:
    # Los dataclass de #3832 no validan tipos en runtime. Fallar de forma segura
    # si un llamador construye un contenedor que no cumple el contrato.
    if type(result) is not SerpApiResult or type(result.pages) is not tuple:
        return False
    if type(result.incomplete) is not bool or type(result.limited) is not bool:
        return False
    if type(result.stop_reason) is not str or result.stop_reason not in _STOP_REASONS:
        return False
    for page in result.pages:
        if type(page) is not SerpApiPage or type(page.reviews) is not tuple:
            return False
        if type(page.number) is not int or page.number < 1:
            return False
    return True


def normalize_serpapi_result(result: SerpApiResult, *, business_data_id: str) -> NormalizationBatchResult:
    """Validar, particionar y deduplicar sin modificar entradas ni hacer E/S.

    Los errores de lote no procesan entradas (input_count=0). Cada rechazo de
    registro informa el primer campo inválido. Los conflictos incluyen TODAS las
    ocurrencias del grupo y también figuran en rejected, nunca en duplicates.
    """
    if not _valid_envelope(result):
        return NormalizationBatchResult(batch_error=NormalizationIssue(None, "result", "invalid_result"))
    flags = dict(incomplete=result.incomplete, limited=result.limited, stop_reason=result.stop_reason)
    if type(business_data_id) is not str or _BUSINESS_ID.fullmatch(business_data_id) is None:
        return NormalizationBatchResult(
            batch_error=NormalizationIssue(None, "business_data_id", "invalid_business_context"), **flags,
        )

    groups: dict[tuple[str, str, str], list[NormalizedExternalReview]] = {}
    rejected: list[RejectedReview] = []
    warnings: list[NormalizationIssue] = []
    total = 0
    for page in result.pages:
        for index, native in enumerate(page.reviews, start=1):
            total += 1
            position = RecordPosition(page.number, index, total)
            try:
                if type(native) is not SerpApiReview or type(native.data) is not dict:
                    raise _InvalidField("record", "invalid_record")
                review = _record(native.data, position, business_data_id)
            except _InvalidField as error:
                issue = NormalizationIssue(position, error.field, error.code)
                rejected.append(RejectedReview(position, (issue,)))
                continue
            if review.author is None:
                warnings.append(NormalizationIssue(position, "user.name", "missing_author"))
            if review.content is None:
                warnings.append(NormalizationIssue(position, "content", "missing_content"))
            groups.setdefault(review.identity, []).append(review)

    with_text: list[NormalizedExternalReview] = []
    without_text: list[NormalizedExternalReview] = []
    duplicates: list[DuplicateReview] = []
    conflicts: list[ConflictingReviews] = []
    for records in groups.values():
        first = records[0]
        if any(record != first for record in records[1:]):
            conflicts.append(ConflictingReviews(tuple(records)))
            for record in records:
                issue = NormalizationIssue(record.position, "record", "conflicting_duplicate")
                rejected.append(RejectedReview(record.position, (issue,)))
            continue
        (with_text if first.content is not None else without_text).append(first)
        duplicates.extend(DuplicateReview(record.position, first.position) for record in records[1:])

    return NormalizationBatchResult(
        input_count=total, with_text=tuple(with_text), without_text=tuple(without_text),
        rejected=tuple(sorted(rejected, key=lambda item: item.position.ordinal)),
        duplicates=tuple(sorted(duplicates, key=lambda item: item.position.ordinal)),
        conflicts=tuple(conflicts), warnings=tuple(warnings), **flags,
    )
