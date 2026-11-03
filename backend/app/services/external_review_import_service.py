"""Manual, bounded import. Admission, HTTP and persistence use separate scopes."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.external_import_config import ExternalImportSettings
from app.db.external_import_schema import ExternalImportSchemaError, verify_external_import_schema
from app.models.external_review_import_attempt import ExternalReviewImportAttempt
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.external_review_import import ExternalReviewImportFailure, ExternalReviewImportResponse
from app.services.external_review_persistence_service import ExternalReviewPersistenceError, ExternalReviewPersistenceService
from app.services.serpapi_client import SerpApiClient, SerpApiError
from app.services.serpapi_normalizer import normalize_serpapi_result


_ERRORS = {
    "unauthorized_context": (403, "El contexto autenticado no está autorizado"),
    "import_disabled": (403, "La importación externa está deshabilitada en el servidor"),
    "connection_unavailable": (404, "La conexión externa no está disponible para este contexto"),
    "persistence_disabled": (403, "La conexión no tiene habilitada la persistencia autorizada"),
    "import_in_progress": (409, "La conexión tiene una operación pendiente de finalización o revisión"),
    "budget_exhausted": (429, "La importación excede el presupuesto de solicitudes del servidor"),
    "admission_unavailable": (503, "No se pudo confirmar la admisión de la importación"),
    "admission_schema_invalid": (503, "El esquema de admisión requiere revisión administrativa"),
    "policy_unavailable": (503, "La política de importación no está disponible"),
    "place_unverified": (502, "No se pudo verificar el establecimiento devuelto por el proveedor"),
    "incomplete_acquisition": (409, "La adquisición está incompleta; no se guardaron reseñas"),
    "normalization_failed": (502, "La respuesta no cumple el contrato de normalización"),
    "provider_timeout": (504, "El proveedor excedió el tiempo de espera"),
    "provider_unavailable": (503, "El proveedor no está disponible para esta operación"),
    "provider_response": (502, "El proveedor no devolvió una respuesta válida para importar"),
    "persistence_rejected": (422, "El lote no cumple los requisitos de persistencia"),
    "persistence_conflict": (409, "No se pudo completar la transacción por concurrencia"),
    "persistence_failed": (503, "No se pudo confirmar la persistencia del lote"),
    "internal_error": (500, "No se pudo completar la importación externa"),
}


class ExternalReviewImportError(Exception):
    def __init__(self, code: str, **details) -> None:
        self.http_status, message = _ERRORS[code]
        self.detail = ExternalReviewImportFailure(code=code, message=message, **details)
        super().__init__(message)


class ExternalReviewImportService:
    def __init__(
        self, sessions: sessionmaker, policy: ExternalImportSettings, *,
        client_factory: Callable[[], SerpApiClient] = SerpApiClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.sessions = sessions
        self.policy = policy
        self.client_factory = client_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def _reserve(self, user: AuthenticatedUser, business: str, operation: str) -> None:
        """Serialize budgets across workers. Never expire an unresolved operation."""
        try:
            with self.sessions() as db:
                connection = db.connection()
                if connection.dialect.name == "sqlite":
                    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
                        raise ExternalReviewImportError("admission_unavailable")
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                elif connection.dialect.name == "postgresql":
                    # Same lock for every worker sharing this provider account/DB.
                    connection.exec_driver_sql("SELECT pg_advisory_xact_lock(32513563)")
                else:
                    raise ExternalReviewImportError("admission_unavailable")
                # Recheck before consumption as well as at startup: fail closed
                # after an out-of-band schema change, without altering that table.
                verify_external_import_schema(connection)
                repository = ReviewRepository(db)
                if not repository.external_actor_is_active(user.id, user.tenant_id, user.rol):
                    raise ExternalReviewImportError("unauthorized_context")
                configured = repository.get_external_connection(user.tenant_id, business)
                if configured is None:
                    raise ExternalReviewImportError("connection_unavailable")
                if not configured.persistence_enabled or not configured.approval_reference or not configured.approval_reference.strip():
                    raise ExternalReviewImportError("persistence_disabled")
                attempt = ExternalReviewImportAttempt
                running = db.scalar(select(attempt.operation_id).where(
                    attempt.tenant_id == user.tenant_id, attempt.source == "Google",
                    attempt.business_data_id == business, attempt.active.is_(True),
                ))
                if running is not None:
                    raise ExternalReviewImportError("import_in_progress")
                now = self.clock()
                recent = select(func.coalesce(func.sum(attempt.reserved_requests), 0)).where(
                    attempt.started_at >= now - timedelta(seconds=self.policy.budget_window_seconds),
                )
                total = db.scalar(recent)
                tenant = db.scalar(recent.where(attempt.tenant_id == user.tenant_id))
                if (total + self.policy.max_pages > self.policy.account_request_budget
                        or tenant + self.policy.max_pages > self.policy.tenant_request_budget):
                    raise ExternalReviewImportError("budget_exhausted")
                db.add(attempt(
                    operation_id=operation, tenant_id=user.tenant_id, source="Google",
                    business_data_id=business, started_at=now,
                    reserved_requests=self.policy.max_pages, active=True, state="running",
                ))
                db.commit()
        except ExternalImportSchemaError:
            raise ExternalReviewImportError("admission_schema_invalid") from None
        except SQLAlchemyError:
            # Admission may have committed; no HTTP has occurred. Manual inspection
            # is required if an attempt remains running. Never retry automatically.
            raise ExternalReviewImportError(
                "admission_unavailable", operation_id=operation,
                control_status="reconciliation_required",
            ) from None

    def _finish(self, operation: str, *, uncertain: bool) -> None:
        with self.sessions() as db:
            attempt = db.get(ExternalReviewImportAttempt, operation)
            if attempt is None:
                raise RuntimeError("Import admission metadata unavailable")
            attempt.state = "unknown" if uncertain else "finished"
            attempt.active = True if uncertain else None
            db.commit()

    def import_reviews(self, user: AuthenticatedUser, business: str) -> ExternalReviewImportResponse:
        if (type(user) is not AuthenticatedUser or user.rol not in ("usuario_negocio", "admin_tenant")
                or type(user.tenant_id) is not int or user.tenant_id < 1
                or type(user.id) is not int or user.id < 1):
            raise ExternalReviewImportError("unauthorized_context")
        if not self.policy.enabled:
            raise ExternalReviewImportError("import_disabled")
        operation = str(uuid4())
        self._reserve(user, business, operation)
        acquired = None
        result = None
        failure = None
        persistence_started = False
        try:
            with self.client_factory() as client:
                acquired = client.fetch_reviews(
                    business, page_size=self.policy.page_size, max_pages=self.policy.max_pages,
                )
            if (not acquired.pages or any(
                    not page.provenance_verified or page.place_data_id != business for page in acquired.pages)):
                raise ExternalReviewImportError("place_unverified")
            if acquired.incomplete:
                raise ExternalReviewImportError("incomplete_acquisition")
            batch = normalize_serpapi_result(acquired, business_data_id=business)
            if batch.batch_error is not None:
                raise ExternalReviewImportError("normalization_failed")
            with self.sessions() as db:
                persistence_started = True
                saved = ExternalReviewPersistenceService(ReviewRepository(db)).persist(
                    batch, current_user=user, business_data_id=business,
                )
            result = ExternalReviewImportResponse(
                operation_id=operation, input_count=saved.input_count, inserted=saved.inserted,
                repeated=saved.repeated, changed=saved.changed, omitted=saved.omitted,
                rejected=saved.rejected, batch_duplicates=saved.batch_duplicates,
                request_count=acquired.request_count, incomplete=saved.incomplete,
                limited=saved.limited, stop_reason=saved.stop_reason,
            )
        except SerpApiError as error:
            acquired = error.partial_result
            code = ("provider_timeout" if error.code == "timeout" else
                    "provider_unavailable" if error.code in {"configuration", "input", "closed", "credentials", "forbidden", "quota", "unavailable", "network"}
                    else "provider_response")
            failure = ExternalReviewImportError(code)
        except ExternalReviewPersistenceError as error:
            code = (error.code if error.code in {"unauthorized_context", "connection_unavailable", "persistence_disabled"}
                    else "persistence_conflict" if error.code in {"concurrent_conflict", "database_busy"}
                    else "persistence_failed" if error.outcome == "unknown" or error.code == "database_error"
                    else "persistence_rejected")
            failure = ExternalReviewImportError(
                code, outcome=error.outcome, committed_count=error.committed_count,
            )
        except ExternalReviewImportError as error:
            failure = error
        except Exception:
            failure = ExternalReviewImportError(
                "internal_error", outcome="unknown" if persistence_started else "rejected",
                committed_count=None if persistence_started else 0,
            )
        uncertain = failure is not None and failure.detail.outcome == "unknown"
        control_status = "reconciliation_required" if uncertain else "released"
        try:
            self._finish(operation, uncertain=uncertain)
        except Exception:
            # A review commit already confirmed stays confirmed even if closing
            # the admission journal fails. Do not claim rollback or retry HTTP.
            control_status = "reconciliation_required"
        if failure is not None:
            failure.detail.operation_id = operation
            failure.detail.control_status = control_status
            if acquired is not None:
                failure.detail.request_count = acquired.request_count
                failure.detail.obtained = acquired.record_count
                failure.detail.incomplete = acquired.incomplete
                failure.detail.limited = acquired.limited
                failure.detail.stop_reason = acquired.stop_reason
            raise failure from None
        result.control_status = control_status
        return result
