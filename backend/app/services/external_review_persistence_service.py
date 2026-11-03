"""Persistencia acotada de DTO normalizados; sin HTTP, activación pública ni IA."""

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import get_args

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.models.review import Review
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.external_review import (
    ConflictingReviews, DuplicateReview, IssueCode, NormalizationBatchResult,
    NormalizationIssue, NormalizedExternalReview, RecordPosition, RejectedReview,
)
from app.schemas.external_review_persistence import ExternalReviewPersistenceResult
from app.schemas.serpapi import StopReason


MAX_OCCURRENCES = 100
MAX_CONTENT_BYTES = 64 * 1024
MAX_BATCH_TEXT_BYTES = 1024 * 1024
_BUSINESS = re.compile(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+")
_ISSUE_FIELDS = {"review_id", "source", "user.name", "extracted_snippet.original", "snippet", "iso_date", "rating", "record", "content"}
_MESSAGES = {
    "invalid_batch": "El lote normalizado no es válido",
    "invalid_record": "Un registro normalizado no es válido para persistencia",
    "batch_limit": "El lote excede el límite de ocurrencias",
    "text_budget": "El lote excede el límite de carga textual",
    "invalid_business": "El contexto de establecimiento no es válido",
    "unauthorized_context": "El contexto autenticado no está autorizado",
    "connection_unavailable": "La conexión externa no está disponible para este contexto",
    "persistence_disabled": "La persistencia externa no está habilitada",
    "incomplete_disabled": "La persistencia de adquisiciones incompletas está deshabilitada",
    "session_in_use": "La sesión contiene otra unidad de trabajo",
    "foreign_keys_disabled": "La conexión no tiene integridad referencial habilitada",
    "integrity": "No se pudo mantener la integridad del lote",
    "concurrent_conflict": "La operación requiere una nueva transacción por concurrencia",
    "database_busy": "La base de datos está ocupada temporalmente",
    "database_error": "No se pudo persistir el lote",
    "commit_unknown": "No se pudo confirmar el resultado del commit; reejecutar es idempotente",
    "rollback_failed": "No se pudo confirmar la finalización de la transacción",
}


class ExternalReviewPersistenceError(Exception):
    """No conserva excepción original, SQL, parámetros, actor ni registros."""

    def __init__(self, code: str, *, outcome: str = "rejected", incomplete: bool | None = None) -> None:
        self.code = code
        self.outcome = outcome
        self.incomplete = incomplete
        self.committed_count = None if outcome == "unknown" else 0
        self.retryable = code in {"concurrent_conflict", "database_busy", "commit_unknown", "rollback_failed"}
        super().__init__(_MESSAGES[code])


def _string(value: object, *, chars: int, byte_limit: int, optional: bool = False) -> int:
    if optional and value is None:
        return 0
    if type(value) is not str or not value.strip() or len(value) > chars or "\x00" in value:
        raise ExternalReviewPersistenceError("invalid_record")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        size = byte_limit + 1
    if size > byte_limit:
        raise ExternalReviewPersistenceError("invalid_record")
    return size


def _position(value: object, total: int) -> None:
    if type(value) is not RecordPosition or any(
        type(number) is not int or not 1 <= number <= MAX_OCCURRENCES
        for number in (value.page, value.index, value.ordinal)
    ) or value.ordinal > total:
        raise ExternalReviewPersistenceError("invalid_batch")


def _issue(value: object, positions: dict[int, RecordPosition]) -> None:
    if type(value) is not NormalizationIssue or type(value.field) is not str or type(value.code) is not str:
        raise ExternalReviewPersistenceError("invalid_batch")
    if value.field not in _ISSUE_FIELDS or value.code not in get_args(IssueCode):
        raise ExternalReviewPersistenceError("invalid_batch")
    _position(value.position, len(positions))
    if positions.get(value.position.ordinal) != value.position:
        raise ExternalReviewPersistenceError("invalid_batch")


def _record_size(row: object, business: str, total: int) -> int:
    if type(row) is not NormalizedExternalReview:
        raise ExternalReviewPersistenceError("invalid_record")
    _position(row.position, total)
    size = _string(row.external_review_id, chars=512, byte_limit=1024)
    if type(row.source) is not str or row.source != "Google" or type(row.business_data_id) is not str or row.business_data_id != business:
        raise ExternalReviewPersistenceError("invalid_record")
    size += len(business) + len("Google")
    size += _string(row.author, chars=255, byte_limit=1020, optional=True)
    size += _string(row.content, chars=MAX_CONTENT_BYTES, byte_limit=MAX_CONTENT_BYTES, optional=True)
    if row.author is not None and row.author.strip() != row.author:
        raise ExternalReviewPersistenceError("invalid_record")
    if type(row.review_date) is not datetime or row.review_date.tzinfo is not timezone.utc:
        raise ExternalReviewPersistenceError("invalid_record")
    if type(row.rating) is not int or not 1 <= row.rating <= 5:
        raise ExternalReviewPersistenceError("invalid_record")
    if row.content is None:
        if row.content_field is not None:
            raise ExternalReviewPersistenceError("invalid_record")
    elif type(row.content_field) is not str or row.content_field not in ("snippet", "extracted_snippet.original") or row.content.strip() != row.content:
        raise ExternalReviewPersistenceError("invalid_record")
    return size + len(row.content_field or "")


def _validate_batch(batch: object, business: object, allow_incomplete: bool) -> None:
    if type(business) is not str or len(business) > 128 or _BUSINESS.fullmatch(business) is None:
        raise ExternalReviewPersistenceError("invalid_business")
    if type(batch) is not NormalizationBatchResult or batch.batch_error is not None:
        raise ExternalReviewPersistenceError("invalid_batch")
    if type(batch.input_count) is not int or not 0 <= batch.input_count <= MAX_OCCURRENCES:
        raise ExternalReviewPersistenceError("batch_limit")
    if type(batch.incomplete) is not bool or type(batch.limited) is not bool or type(batch.stop_reason) is not str or batch.stop_reason not in get_args(StopReason):
        raise ExternalReviewPersistenceError("invalid_batch")
    if batch.incomplete != (batch.stop_reason != "no_next_token") or batch.limited != (batch.stop_reason == "max_pages"):
        raise ExternalReviewPersistenceError("invalid_batch")
    if batch.incomplete and not allow_incomplete:
        raise ExternalReviewPersistenceError("incomplete_disabled", incomplete=True)
    categories = (batch.with_text, batch.without_text, batch.rejected, batch.duplicates)
    if any(type(items) is not tuple or len(items) > MAX_OCCURRENCES for items in (*categories, batch.conflicts)):
        raise ExternalReviewPersistenceError("batch_limit")
    if type(batch.warnings) is not tuple or len(batch.warnings) > 2 * batch.input_count:
        raise ExternalReviewPersistenceError("invalid_batch")
    if sum(map(len, categories)) != batch.input_count:
        raise ExternalReviewPersistenceError("invalid_batch")
    positions: dict[int, RecordPosition] = {}
    for items, kind in zip(categories, (NormalizedExternalReview, NormalizedExternalReview, RejectedReview, DuplicateReview)):
        for item in items:
            if type(item) is not kind:
                raise ExternalReviewPersistenceError("invalid_batch")
            _position(item.position, batch.input_count)
            if item.position.ordinal in positions:
                raise ExternalReviewPersistenceError("invalid_batch")
            positions[item.position.ordinal] = item.position
    if set(positions) != set(range(1, batch.input_count + 1)):
        raise ExternalReviewPersistenceError("invalid_batch")
    identities = set()
    accepted_positions = set()
    size = len(business)
    for row in (*batch.with_text, *batch.without_text):
        size += _record_size(row, business, batch.input_count)
        if row.identity in identities:
            raise ExternalReviewPersistenceError("invalid_batch")
        identities.add(row.identity)
        accepted_positions.add(row.position)
    if any(row.content is None for row in batch.with_text) or any(row.content is not None for row in batch.without_text):
        raise ExternalReviewPersistenceError("invalid_batch")
    rejected_positions = set()
    conflict_positions = set()
    for rejected in batch.rejected:
        if type(rejected.issues) is not tuple or not 1 <= len(rejected.issues) <= 4:
            raise ExternalReviewPersistenceError("invalid_batch")
        for issue in rejected.issues:
            _issue(issue, positions)
            if issue.position != rejected.position:
                raise ExternalReviewPersistenceError("invalid_batch")
            if issue.code == "conflicting_duplicate":
                rejected_positions.add(rejected.position)
    for duplicate in batch.duplicates:
        _position(duplicate.kept_position, batch.input_count)
        if duplicate.kept_position not in accepted_positions:
            raise ExternalReviewPersistenceError("invalid_batch")
    for group in batch.conflicts:
        if type(group) is not ConflictingReviews or type(group.records) is not tuple or not 2 <= len(group.records) <= batch.input_count:
            raise ExternalReviewPersistenceError("invalid_batch")
        key = None
        for row in group.records:
            size += _record_size(row, business, batch.input_count)
            if row.position not in rejected_positions or row.position in conflict_positions:
                raise ExternalReviewPersistenceError("invalid_batch")
            conflict_positions.add(row.position)
            if key is None:
                key = row.identity
            if row.identity != key or row.identity in identities:
                raise ExternalReviewPersistenceError("invalid_batch")
        identities.add(key)
    if conflict_positions != rejected_positions:
        raise ExternalReviewPersistenceError("invalid_batch")
    for issue in batch.warnings:
        _issue(issue, positions)
        if issue.code not in ("missing_author", "missing_content"):
            raise ExternalReviewPersistenceError("invalid_batch")
    if size > MAX_BATCH_TEXT_BYTES:
        raise ExternalReviewPersistenceError("text_budget")


def _fingerprint(row: NormalizedExternalReview) -> str:
    values = [row.source, row.business_data_id, row.external_review_id, row.author, row.content,
              row.review_date.isoformat(timespec="microseconds"), row.rating, row.content_field]
    canonical = json.dumps(values, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "v1:" + hashlib.sha256(canonical).hexdigest()


def _database_failure(error: Exception, committing: bool) -> tuple[str, str]:
    original = getattr(error, "orig", None)
    sqlite_code = getattr(original, "sqlite_errorcode", None)
    state = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if type(sqlite_code) is int and sqlite_code & 255 in (5, 6):
        return "database_busy", "rolled_back"
    if state in ("40001", "40P01"):
        return "concurrent_conflict", "rolled_back"
    if isinstance(error, IntegrityError):
        constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
        if sqlite_code == 2067 or (state == "23505" and constraint == "uq_external_review_identity"):
            return "concurrent_conflict", "rolled_back"
        return "integrity", "rolled_back"
    return ("commit_unknown", "unknown") if committing else ("database_error", "rolled_back")


class ExternalReviewPersistenceService:
    def __init__(self, repository: ReviewRepository, *, allow_incomplete: bool = False) -> None:
        if type(allow_incomplete) is not bool:
            raise ExternalReviewPersistenceError("invalid_batch")
        self.repository = repository
        self.allow_incomplete = allow_incomplete  # Opción de composición interna, no de solicitud.

    def persist(self, batch: NormalizationBatchResult, *, current_user: AuthenticatedUser, business_data_id: str) -> ExternalReviewPersistenceResult:
        _validate_batch(batch, business_data_id, self.allow_incomplete)
        if type(current_user) is not AuthenticatedUser or current_user.rol not in ("usuario_negocio", "admin_tenant") or any(
            type(value) is not int or value < 1 for value in (current_user.id, current_user.tenant_id)
        ):
            raise ExternalReviewPersistenceError("unauthorized_context")
        db = self.repository.db
        # Exigir una sesión exclusiva antes de su primer autobegin. Una sesión
        # con lecturas previas o escrituras ya flush también pertenece al llamador.
        # Una Connection externa podría volver commit() un no-op de la sesión.
        if not isinstance(db.get_bind(), Engine) or not db.is_active or db.in_transaction() or db.new or db.dirty or db.deleted:
            raise ExternalReviewPersistenceError("session_in_use")
        failure = None
        committing = False
        try:
            connection = db.connection()
            if connection.dialect.name == "sqlite":
                if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
                    raise ExternalReviewPersistenceError("foreign_keys_disabled")
                if not connection.connection.driver_connection.in_transaction:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
            tenant = current_user.tenant_id
            if not self.repository.external_actor_is_active(current_user.id, tenant, current_user.rol):
                raise ExternalReviewPersistenceError("unauthorized_context")
            configured = self.repository.get_external_connection(tenant, business_data_id)
            if configured is None:
                raise ExternalReviewPersistenceError("connection_unavailable")
            if not configured.persistence_enabled or not configured.approval_reference or not configured.approval_reference.strip():
                raise ExternalReviewPersistenceError("persistence_disabled")
            inserted = repeated = 0
            changed = []
            for row in batch.with_text:
                fingerprint = _fingerprint(row)
                stored = self.repository.get_external_fingerprint(tenant, business_data_id, row.external_review_id)
                if stored is not None:
                    if stored == fingerprint:
                        repeated += 1
                    else:
                        changed.append(row.position)
                    continue
                review = Review(
                    tenant_id=tenant, autor=row.author, contenido=row.content,
                    fecha=row.review_date.replace(tzinfo=None), fuente=row.source,
                    puntuacion=row.rating, estado="nueva", categoria=None,
                    resumen=None, tema=None, prioridad=None,
                )
                self.repository.add_external_review(
                    review, business_data_id=business_data_id,
                    external_review_id=row.external_review_id, fingerprint=fingerprint,
                )
                inserted += 1
            result = ExternalReviewPersistenceResult(
                input_count=batch.input_count, inserted=inserted,
                repeated=repeated + len(batch.duplicates), changed=len(changed),
                omitted=len(batch.without_text), rejected=len(batch.rejected),
                batch_duplicates=len(batch.duplicates), incomplete=batch.incomplete,
                limited=batch.limited, stop_reason=batch.stop_reason,
                changed_positions=tuple(changed), warnings=batch.warnings,
            )
            committing = True
            db.commit()
            return result  # Sin refresh ni acceso ORM después del commit.
        except ExternalReviewPersistenceError as error:
            failure = (error.code, error.outcome)
        except Exception as error:
            failure = _database_failure(error, committing)
        try:
            db.rollback()
        except Exception:
            failure = ("rollback_failed", "unknown")
        # Fuera del except: no encadenar excepciones SQL con parámetros sensibles.
        raise ExternalReviewPersistenceError(failure[0], outcome=failure[1], incomplete=batch.incomplete)
