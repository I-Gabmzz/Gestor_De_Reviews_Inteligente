"""Repositorio de acceso a datos para la entidad Review."""

from datetime import date, datetime, time, timedelta
from functools import wraps

from sqlalchemy import desc, event, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.review import Review
from app.models.external_review_connection import ExternalReviewConnection
from app.models.external_review_identity import ExternalReviewIdentity
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.ai import AIResult, ClassificationResult, PriorityResult, SolutionResult, SummaryResult, TopicResult
from app.schemas.review import ReviewStatus


def _private_sql_operation(method):
    """Redactar el echo SQL sólo durante esta operación, sin tocar loggers.

    SQLAlchemy 2.x no oculta filas con hide_parameters. Se interceptan los dos
    emisores de la Connection, no niveles, handlers, filtros ni el Engine. El
    evento local cubre también las conexiones abiertas por refresh tras commit.
    Estos emisores son internos: conservar las regresiones al actualizar SQLA.
    """
    @wraps(method)
    def execute(self, *args, **kwargs):
        db = self.db
        if not isinstance(db, Session) or db.info.get("_review_private_sql"):
            return method(self, *args, **kwargs)
        saved = {}

        def protect(connection):
            if connection in saved:
                return
            saved[connection] = {}
            for name in ("_log_info", "_log_debug"):
                saved[connection][name] = (name in connection.__dict__, connection.__dict__.get(name))
                original = getattr(connection, name)

                def safe_log(message, *values, _emit=original, **options):
                    kind = "result" if message == "Row %r" else "activity"
                    _emit("ReviewRepository %s: SQL %s [details redacted]", method.__name__, kind)

                setattr(connection, name, safe_log)

        def after_begin(session, transaction, connection):
            protect(connection)

        db.info["_review_private_sql"] = True
        event.listen(db, "after_begin", after_begin)
        try:
            if db.in_transaction() and db.is_active:
                protect(db.connection())
            return method(self, *args, **kwargs)
        finally:
            event.remove(db, "after_begin", after_begin)
            for connection, attributes in saved.items():
                for name, (existed, value) in attributes.items():
                    if existed:
                        setattr(connection, name, value)
                    else:
                        delattr(connection, name)
            db.info.pop("_review_private_sql", None)

    return execute


class ReviewRepository:
    """Centraliza la lectura y escritura de reviews."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @_private_sql_operation
    def external_actor_is_active(self, user_id: int, tenant_id: int, role: str) -> bool:
        statement = select(User.id).join(Tenant, Tenant.id == User.tenant_id).where(
            User.id == user_id, User.tenant_id == tenant_id, User.rol == role,
            func.lower(User.estado) == "activo", Tenant.estado == "activo",
        )
        return self.db.scalar(statement) is not None

    @_private_sql_operation
    def get_external_connection(self, tenant_id: int, business_data_id: str) -> ExternalReviewConnection | None:
        statement = select(ExternalReviewConnection).where(
            ExternalReviewConnection.tenant_id == tenant_id,
            ExternalReviewConnection.source == "Google",
            ExternalReviewConnection.business_data_id == business_data_id,
        ).with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(statement)

    @_private_sql_operation
    def get_external_fingerprint(self, tenant_id: int, business_data_id: str, external_review_id: str) -> str | None:
        statement = select(ExternalReviewIdentity.import_fingerprint).where(
            ExternalReviewIdentity.tenant_id == tenant_id,
            ExternalReviewIdentity.source == "Google",
            ExternalReviewIdentity.business_data_id == business_data_id,
            ExternalReviewIdentity.external_review_id == external_review_id,
        )
        return self.db.scalar(statement)

    @_private_sql_operation
    def add_external_review(self, review: Review, *, business_data_id: str, external_review_id: str, fingerprint: str) -> None:
        """Sólo flush; el servicio es dueño del único commit y del rollback."""
        self.db.add(review)
        self.db.flush()
        self.db.add(ExternalReviewIdentity(
            review_id=review.id, tenant_id=review.tenant_id, source="Google",
            business_data_id=business_data_id, external_review_id=external_review_id,
            import_fingerprint=fingerprint,
        ))
        self.db.flush()

    @_private_sql_operation
    def list_by_tenant(
        self,
        tenant_id: int,
        busqueda: str | None = None,
        *,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        puntuacion: int | None = None,
        estado: str | None = None,
        fuente: str | None = None,
    ) -> list[Review]:
        statement = (
            select(Review)
            .where(Review.tenant_id == tenant_id)
            .order_by(Review.fecha.desc(), Review.id.desc())
        )
        if busqueda:
            statement = statement.where(Review.contenido.icontains(busqueda, autoescape=True))
        if fecha_desde is not None:
            statement = statement.where(Review.fecha >= datetime.combine(fecha_desde, time.min))
        # date.max incluye todas las fechas representables y no tiene un dia siguiente.
        if fecha_hasta is not None and fecha_hasta < date.max:
            end_exclusive = datetime.combine(fecha_hasta + timedelta(days=1), time.min)
            statement = statement.where(Review.fecha < end_exclusive)
        if puntuacion is not None:
            statement = statement.where(Review.puntuacion == puntuacion)
        if estado is not None:
            statement = statement.where(Review.estado == estado)
        if fuente is not None:
            statement = statement.where(Review.fuente == fuente)
        return list(self.db.scalars(statement))

    @_private_sql_operation
    def get_by_id_for_tenant(self, review_id: int, tenant_id: int) -> Review | None:
        statement = select(Review).where(
            Review.id == review_id,
            Review.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    @_private_sql_operation
    def update(self, review: Review, changes: dict[str, object]) -> Review:
        """Persiste los campos validados de una review del tenant autorizado."""
        # Una propuesta anterior deja de ser vigente al cambiar el comentario.
        if "contenido" in changes and changes["contenido"] != review.contenido:
            review.solucion = None
        for field, value in changes.items():
            setattr(review, field, value)

        try:
            self.db.commit()
            self.db.refresh(review)
            return review
        except SQLAlchemyError:
            self.db.rollback()
            raise

    @_private_sql_operation
    def update_status(self, review: Review, status: ReviewStatus) -> Review:
        review.estado = status.value
        self.db.commit()
        self.db.refresh(review)
        return review

    @_private_sql_operation
    def save_ai_result(
        self,
        review_id: int,
        tenant_id: int,
        result: AIResult,
        *,
        expected_content: str | None = None,
    ) -> Review | None:
        """Guarda un resultado validado sin sobrescribir los demás campos.

        El tenant debe proceder del contexto autenticado, nunca del proveedor.
        None representa tanto una review ajena como una inexistente.
        """
        allowed_types = (ClassificationResult, SummaryResult, TopicResult, PriorityResult, SolutionResult)
        if type(result) not in allowed_types:
            raise TypeError("Se requiere un resultado de IA del contrato común")
        # Revalidar impide persistir instancias construidas sin validación o mutadas.
        validated = type(result).model_validate(result.model_dump())
        review = self.get_by_id_for_tenant(review_id, tenant_id)
        if review is None:
            return None
        try:
            statement = (
                update(Review)
                .where(Review.id == review_id, Review.tenant_id == tenant_id)
                .values(**validated.model_dump())
                .execution_options(synchronize_session=False)
            )
            if expected_content is not None:
                statement = statement.where(Review.contenido == expected_content)
            saved = self.db.execute(statement)
            if saved.rowcount != 1:
                self.db.rollback()
                return None
            if type(validated) is PriorityResult and validated.prioridad == "Alta":
                notification = NotificationRepository(self.db).add_for_high_review(review_id, tenant_id)
                if notification is None:
                    raise SQLAlchemyError("No fue posible asociar el aviso a la prioridad guardada")
            self.db.commit()
            self.db.refresh(review)
            return review
        except SQLAlchemyError:
            self.db.rollback()
            raise

    @_private_sql_operation
    def count_by_tenant(self, tenant_id: int) -> int:
        """Cuenta las reseñas pertenecientes a un tenant."""
        statement = select(func.count()).select_from(Review).where(Review.tenant_id == tenant_id)
        return int(self.db.scalar(statement) or 0)

    @_private_sql_operation
    def average_score_by_tenant(self, tenant_id: int) -> float | None:
        """Calcula el promedio de puntuación para las reseñas de un tenant."""
        statement = select(func.avg(Review.puntuacion)).where(Review.tenant_id == tenant_id)
        average = self.db.scalar(statement)
        return float(average) if average is not None else None

    @_private_sql_operation
    def count_new_by_tenant(self, tenant_id: int) -> int:
        """Cuenta las reseñas nuevas de un tenant."""
        statement = (
            select(func.count())
            .select_from(Review)
            .where(
                Review.tenant_id == tenant_id,
                func.lower(Review.estado) == "nueva",
            )
        )
        return int(self.db.scalar(statement) or 0)

    @_private_sql_operation
    def list_recent_by_tenant(self, tenant_id: int, limit: int = 5) -> list[Review]:
        """Obtiene las reseñas más recientes de un tenant."""
        statement = (
            select(Review)
            .where(Review.tenant_id == tenant_id)
            .order_by(desc(Review.fecha), desc(Review.id))
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    @_private_sql_operation
    def create_many(self, reviews: list[Review]) -> list[Review]:
        """Inserta una lista de reviews en una sola transacción."""
        if not reviews:
            return []

        try:
            self.db.add_all(reviews)
            self.db.commit()
            for review in reviews:
                self.db.refresh(review)
            return reviews
        except SQLAlchemyError:
            self.db.rollback()
            raise

    @_private_sql_operation
    def create(self, review: Review) -> Review:
        """Inserta una review en una transacción."""
        try:
            self.db.add(review)
            self.db.commit()
            self.db.refresh(review)
            return review
        except SQLAlchemyError:
            self.db.rollback()
            raise
