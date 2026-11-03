"""Alta manual de un negocio y su administrador; no se ejecuta al desplegar."""

import argparse
from dataclasses import dataclass
from getpass import GetPassWarning, getpass
import sys
import warnings

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.connection import create_database_engine
from app.models import Tenant, User


@dataclass(frozen=True)
class BusinessSetupResult:
    tenant_id: int
    user_id: int
    business_created: bool
    administrator_created: bool


def read_secret(prompt: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        return getpass(prompt)


def external_database_url(value: str) -> URL:
    """Exige la URL externa de Render y TLS, sin incluir secretos en errores."""
    try:
        url = make_url(value.strip())
        if (
            url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}
            or not url.host or not url.host.endswith(".render.com")
            or not url.database or not url.username or not url.password
        ):
            raise ValueError
        mode = url.query.get("sslmode", "require")
        if mode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError
        return url.set(drivername="postgresql+psycopg").update_query_dict({
            "sslmode": mode, "connect_timeout": "15",
        })
    except (ArgumentError, ValueError, TypeError):
        raise ValueError("Copia la External Database URL completa de Render; se requiere TLS") from None


def create_business(
    database: Engine, *, name: str, email: str, password: str,
) -> BusinessSetupResult:
    name = name.strip()
    if not name or len(name) > 255:
        raise ValueError("El nombre del negocio debe tener entre 1 y 255 caracteres")
    email = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    if len(email) > 320 or len(password) < 12:
        raise ValueError("El correo no debe exceder 320 caracteres y la contraseña necesita al menos 12")
    hashed = get_password_hash(password)
    with Session(database) as db, db.begin():
        if database.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(32513946)"))
        elif database.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise ValueError("Motor de base de datos no soportado")
        matches = list(db.scalars(select(Tenant).where(Tenant.nombre == name)))
        if len(matches) > 1:
            raise ValueError("Hay varios negocios con ese nombre; revisa sus identificadores antes de continuar")
        tenant = matches[0] if matches else None
        business_created = tenant is None
        if tenant is None:
            tenant = Tenant(nombre=name, estado="activo")
            db.add(tenant)
            db.flush()
        elif tenant.estado != "activo":
            raise ValueError("El negocio existente está inactivo; no se modificó")
        user = db.scalar(select(User).where(User.correo == email))
        administrator_created = user is None
        if user is None:
            user = User(tenant_id=tenant.id, nombre="Administrador del negocio",
                        correo=email, password_hash=hashed, rol="admin_tenant", estado="activo")
            db.add(user)
            db.flush()
        elif (user.tenant_id, user.rol, user.estado) != (tenant.id, "admin_tenant", "activo"):
            raise ValueError("El correo pertenece a otra cuenta o tiene permisos distintos; no se modificó")
        return BusinessSetupResult(tenant.id, user.id, business_created, administrator_created)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crear un negocio y su administrador en PostgreSQL de Render")
    parser.add_argument("--name", required=True, help="Nombre del negocio")
    parser.add_argument("--email", required=True, help="Correo del administrador de demostración")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print("Ejecuta este comando en una terminal interactiva para introducir los secretos en privado.")
        return 2
    database = None
    try:
        url = external_database_url(read_secret("External Database URL de Render (entrada oculta): "))
        print(f"Destino: {url.host} / {url.database}")
        print(f"Negocio: {args.name} | Administrador del negocio: {args.email}")
        if input("Escribe CREAR para confirmar el alta: ").strip() != "CREAR":
            print("Alta cancelada.")
            return 0
        password = read_secret("Contraseña del administrador (mínimo 12 caracteres): ")
        if password != read_secret("Repite la contraseña: "):
            raise ValueError("Las contraseñas no coinciden")
        database = create_database_engine(url)
        result = create_business(database, name=args.name, email=args.email, password=password)
        print(f"Negocio listo. ID: {result.tenant_id}. Administrador ID: {result.user_id}.")
        print(f"Correo de acceso: {args.email.lower()}")
        if not result.administrator_created:
            print("La cuenta ya existía: conserva su contraseña y sus datos anteriores.")
        print("No se cargaron reseñas ni se habilitó la importación externa.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nAlta cancelada.")
        return 130
    except GetPassWarning:
        print("No se pudo ocultar la entrada. Usa una terminal interactiva; no se realizó el alta.")
        return 2
    except (ValueError, SQLAlchemyError):
        print("No se completó el alta. Revisa los datos, la conexión y posibles cuentas existentes. No se guardaron cambios parciales.")
        return 1
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
