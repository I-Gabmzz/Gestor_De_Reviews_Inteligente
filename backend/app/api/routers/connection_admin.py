"""Administración general: cuentas de negocio y conexiones Google."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.api.dependencies import bearer_scheme, get_current_user
from app.api.routers.external_reviews import ImportSessions
from app.models import ExternalReviewConnection, User
from app.schemas.auth import AuthenticatedUser
from app.schemas.connection_admin import (
    AdminAccountInput, AdminAccountRead, AdminConnectionList, AdminConnectionRead,
    GoogleConnectionInput, GoogleConnectionStateInput,
)
from app.schemas.tenant import TenantRead
from app.schemas.user import UserRead
from app.services.external_connection_admin_service import (
    ConnectionAdminError, configure_connection, connection_read, create_business_account,
    get_tenant, require_admin, set_connection_state,
)
from app.services.google_maps_link_service import GoogleMapsLinkError, GoogleMapsLinkResolver


class PrivateAdminRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as error:
                # FastAPI puede incluir el cuerpo completo, incluida la contraseña,
                # al informar campos faltantes o inválidos. Devolver sólo diagnóstico.
                issues = [{key: item[key] for key in ("loc", "msg", "type")} for item in error.errors()]
                raise HTTPException(422, detail=issues) from None
            except ConnectionAdminError as error:
                raise HTTPException(error.status, detail=str(error)) from None
            except GoogleMapsLinkError as error:
                raise HTTPException(422, detail=str(error)) from None
            except IntegrityError:
                raise HTTPException(409, detail="La cuenta o conexión ya existe o cambió mientras guardabas. Actualiza la lista.") from None
            except SQLAlchemyError:
                raise HTTPException(503, detail="No pudimos confirmar el guardado. Actualiza la lista y comprueba el resultado antes de repetir.") from None
        return private_handler


router = APIRouter(prefix="/admin", tags=["administración general"], route_class=PrivateAdminRoute)


def get_connection_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    sessions: ImportSessions,
) -> AuthenticatedUser:
    with sessions() as db:
        user = get_current_user(credentials, db)
        require_admin(db, user.id)
    return user


Admin = Annotated[AuthenticatedUser, Depends(get_connection_admin)]


def get_maps_resolver() -> GoogleMapsLinkResolver:
    return GoogleMapsLinkResolver()


Resolver = Annotated[GoogleMapsLinkResolver, Depends(get_maps_resolver)]


def _resolve(resolver: GoogleMapsLinkResolver, url: str | None, confirmed: bool) -> str | None:
    if not url or not url.strip():
        return None
    if not confirmed:
        raise ConnectionAdminError("Confirma que la ficha de Google Maps corresponde al negocio seleccionado.", 422)
    return resolver.resolve(url)


@router.get("/google-connections", response_model=AdminConnectionList)
def list_connections(user: Admin, sessions: ImportSessions, tenant_id: Annotated[int, Query(gt=0)]):
    with sessions() as db:
        require_admin(db, user.id)
        tenant = get_tenant(db, tenant_id, active=False)
        rows = db.scalars(select(ExternalReviewConnection).where(
            ExternalReviewConnection.tenant_id == tenant_id, ExternalReviewConnection.source == "Google",
        ).order_by(ExternalReviewConnection.business_data_id))
        users = db.scalars(select(User).where(User.tenant_id == tenant_id).order_by(User.id))
        return AdminConnectionList(tenant=TenantRead.model_validate(tenant),
                                   connections=[connection_read(row) for row in rows],
                                   users=[UserRead.model_validate(row) for row in users])


@router.post("/google-connections", response_model=AdminConnectionRead)
def link_connection(data: GoogleConnectionInput, user: Admin, sessions: ImportSessions, resolver: Resolver):
    with sessions() as db:
        require_admin(db, user.id)
        name = get_tenant(db, data.tenant_id).nombre
        database = db.get_bind()
    # Autenticación y lecturas cerradas antes de cualquier E/S hacia Google.
    business = _resolve(resolver, data.google_maps_url, data.confirmed)
    if not business:
        raise ConnectionAdminError("Pega el enlace de la ficha de Google Maps.", 422)
    configure_connection(database, tenant_id=data.tenant_id, expected_name=name, business_data_id=business,
                         approval_reference=f"Vinculación aprobada desde Administración general por usuario {user.id}",
                         admin_id=user.id)
    with sessions() as db:
        return connection_read(db.get(ExternalReviewConnection, (data.tenant_id, "Google", business)))


@router.patch("/google-connections", response_model=AdminConnectionRead)
def change_connection(data: GoogleConnectionStateInput, user: Admin, sessions: ImportSessions):
    with sessions() as db:
        database = db.get_bind()
    set_connection_state(database, admin_id=user.id, tenant_id=data.tenant_id,
                         business=data.business_data_id, enabled=data.enabled)
    with sessions() as db:
        return connection_read(db.get(ExternalReviewConnection, (data.tenant_id, "Google", data.business_data_id)))


@router.post("/business-accounts", response_model=AdminAccountRead, status_code=201)
def create_account(data: AdminAccountInput, user: Admin, sessions: ImportSessions, resolver: Resolver):
    password = data.password.get_secret_value()
    if not 12 <= len(password) <= 1024:
        raise ConnectionAdminError("La contraseña debe tener entre 12 y 1024 caracteres.", 422)
    if bool(data.tenant_id) == bool((data.business_name or "").strip()):
        raise ConnectionAdminError("Selecciona un negocio existente o escribe el nombre de uno nuevo.", 422)
    with sessions() as db:
        require_admin(db, user.id)
        if data.tenant_id:
            get_tenant(db, data.tenant_id)
        database = db.get_bind()
    business = _resolve(resolver, data.google_maps_url, data.confirmed)
    return create_business_account(database, admin_id=user.id, tenant_id=data.tenant_id,
        business_name=data.business_name, nombre=data.nombre, correo=str(data.correo), password=password,
        rol=data.rol, business_data_id=business)
