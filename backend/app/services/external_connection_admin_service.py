"""Altas y conexiones administrativas atómicas, sin importar reseñas."""

from contextlib import contextmanager
import re
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.models import ExternalReviewConnection, ExternalReviewImportAttempt, Tenant, User
from app.schemas.connection_admin import AdminAccountRead, AdminConnectionRead
from app.schemas.tenant import TenantRead
from app.schemas.user import UserRead


class ConnectionAdminError(ValueError):
    def __init__(self, message: str, status: int = 409):
        self.status = status
        super().__init__(message)


def require_admin(db: Session, identifier: int) -> None:
    actor = db.get(User, identifier, populate_existing=True)
    if actor is None or (actor.rol, actor.tenant_id) != ("admin_general", None) or actor.estado.lower() != "activo":
        raise ConnectionAdminError("Se requiere una cuenta activa de administrador general.", 403)


@contextmanager
def _write(database: Engine, admin_id: int | None = None):
    with Session(database) as db, db.begin():
        if database.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(32513563)"))
        elif database.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise ConnectionAdminError("Motor de base de datos no soportado.", 422)
        if admin_id is not None:
            require_admin(db, admin_id)
        yield db


def get_tenant(db: Session, tenant_id: int, *, active: bool = True) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise ConnectionAdminError("No se encontró el negocio seleccionado.", 404)
    if active and tenant.estado != "activo":
        raise ConnectionAdminError("El negocio está inactivo.", 409)
    return tenant


def connection_read(row: ExternalReviewConnection) -> AdminConnectionRead:
    return AdminConnectionRead(business_data_id=row.business_data_id, enabled=row.persistence_enabled,
                              google_maps_url=f"https://www.google.com/maps/place/data=!4m2!1s{row.business_data_id}!1b1")


def _no_pending(db: Session, tenant_id: int) -> None:
    pending = db.scalar(select(ExternalReviewImportAttempt.operation_id).where(
        ExternalReviewImportAttempt.tenant_id == tenant_id, ExternalReviewImportAttempt.active.is_(True)))
    if pending is not None:
        raise ConnectionAdminError("Hay una importación pendiente de revisión; no se modificó la conexión.")


def _enable(db: Session, tenant_id: int, business: str, approval: str) -> tuple[ExternalReviewConnection, bool]:
    _no_pending(db, tenant_id)
    connections = list(db.scalars(select(ExternalReviewConnection).where(
        ExternalReviewConnection.tenant_id == tenant_id, ExternalReviewConnection.source == "Google")))
    if any(row.business_data_id != business and row.persistence_enabled for row in connections):
        raise ConnectionAdminError("El negocio ya tiene otra conexión Google activa. Paúsala antes de vincular otra ficha.")
    configured = next((row for row in connections if row.business_data_id == business), None)
    created = configured is None
    if created:
        configured = ExternalReviewConnection(tenant_id=tenant_id, source="Google", business_data_id=business)
        db.add(configured)
    if not configured.persistence_enabled:
        configured.approval_reference = approval.strip()
        configured.persistence_enabled = True
    return configured, created


def configure_connection(database: Engine, *, tenant_id: int, expected_name: str, business_data_id: str,
                         approval_reference: str, admin_id: int | None = None) -> bool:
    if (type(tenant_id) is not int or tenant_id < 1 or not expected_name.strip() or len(expected_name) > 255
            or len(business_data_id) > 128 or re.fullmatch(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+", business_data_id) is None
            or not approval_reference.strip() or len(approval_reference) > 255):
        raise ConnectionAdminError("Revisa el negocio, el identificador de Google y la referencia de aprobación.", 422)
    with _write(database, admin_id) as db:
        tenant = get_tenant(db, tenant_id)
        if tenant.nombre != expected_name:
            raise ConnectionAdminError("El ID y el nombre no corresponden al negocio; vuelve a seleccionarlo.")
        _, created = _enable(db, tenant_id, business_data_id, approval_reference)
        return created


def set_connection_state(database: Engine, *, admin_id: int, tenant_id: int, business: str, enabled: bool) -> None:
    with _write(database, admin_id) as db:
        get_tenant(db, tenant_id, active=enabled)
        row = db.get(ExternalReviewConnection, (tenant_id, "Google", business))
        if row is None:
            raise ConnectionAdminError("No se encontró la conexión seleccionada.", 404)
        if enabled:
            _enable(db, tenant_id, business, f"Habilitada desde Administración general por usuario {admin_id}")
        else:
            _no_pending(db, tenant_id)
            row.persistence_enabled = False


def create_business_account(database: Engine, *, admin_id: int, tenant_id: int | None,
                            business_name: str | None, nombre: str, correo: str, password: str,
                            rol: str, business_data_id: str | None = None) -> AdminAccountRead:
    name = (business_name or "").strip()
    if (bool(tenant_id) == bool(name) or not nombre.strip() or len(nombre.strip()) > 255
            or len(name) > 255 or not 12 <= len(password) <= 1024
            or rol not in ("admin_tenant", "usuario_negocio")):
        raise ConnectionAdminError("Selecciona un negocio o crea uno nuevo. La contraseña debe tener al menos 12 caracteres.", 422)
    email = str(TypeAdapter(EmailStr).validate_python(correo)).lower()
    hashed = get_password_hash(password)
    with _write(database, admin_id) as db:
        if db.scalar(select(User.id).where(func.lower(User.correo) == email)) is not None:
            raise ConnectionAdminError("Ya existe una cuenta con ese correo; sus datos no se modificaron.")
        if tenant_id is not None:
            tenant = get_tenant(db, tenant_id)
        else:
            if db.scalar(select(Tenant.id).where(func.lower(Tenant.nombre) == name.lower())) is not None:
                raise ConnectionAdminError("Ya existe un negocio con ese nombre. Selecciónalo en la lista.")
            tenant = Tenant(nombre=name, estado="activo")
            db.add(tenant)
            db.flush()
        configured = None
        if business_data_id:
            configured, _ = _enable(db, tenant.id, business_data_id,
                                    f"Vinculación aprobada desde Administración general por usuario {admin_id}")
        user = User(tenant_id=tenant.id, nombre=nombre.strip(), correo=email, password_hash=hashed,
                    rol=rol, estado="activo")
        db.add(user)
        db.flush()
        return AdminAccountRead(tenant=TenantRead.model_validate(tenant), user=UserRead.model_validate(user),
                                connection=connection_read(configured) if configured else None)
