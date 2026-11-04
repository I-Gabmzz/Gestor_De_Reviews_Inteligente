"""Alta inicial y manual de administración general; nunca se ejecuta al desplegar."""

import argparse
from getpass import GetPassWarning
import sys
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.db.connection import create_database_engine
from app.models import User
from scripts.create_business import external_database_url, read_secret


def create_initial_general_admin(database, *, email: str, password: str) -> int:
    email = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    if not 12 <= len(password) <= 1024 or len(email) > 320:
        raise ValueError("La contraseña necesita al menos 12 caracteres y el correo debe ser válido.")
    hashed = get_password_hash(password)
    with Session(database) as db, db.begin():
        if database.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(32513947)"))
        elif database.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise ValueError("Motor no soportado.")
        existing = db.scalar(select(User).where(func.lower(User.correo) == email))
        if existing is not None:
            if (existing.rol, existing.tenant_id, existing.estado) != ("admin_general", None, "activo"):
                raise ValueError("El correo ya pertenece a otra cuenta; no se modificó.")
            return existing.id
        if db.scalar(select(User.id).where(User.rol == "admin_general")) is not None:
            raise ValueError("Ya existe un administrador general. Revisa esa cuenta antes de crear otra.")
        user = User(nombre="Administrador general", correo=email, password_hash=hashed,
                    tenant_id=None, rol="admin_general", estado="activo")
        db.add(user)
        db.flush()
        return user.id


def main(argv=None):
    parser = argparse.ArgumentParser(description="Crear la primera cuenta de administración general")
    parser.add_argument("--email", help="Correo de acceso del administrador general")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print("Ejecuta el comando en una terminal interactiva para introducir los secretos en privado.")
        return 2
    database = None
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email or input("Correo de acceso del administrador general: ").strip())).lower()
        url = external_database_url(read_secret("External Database URL de Render (entrada oculta): "))
        print(f"Destino: {url.host} / {url.database}")
        print(f"Cuenta: {email} | Rol: Administrador general")
        if input("Escribe CREAR ADMIN para confirmar: ").strip() != "CREAR ADMIN":
            print("Alta cancelada.")
            return 0
        password = read_secret("Contraseña inicial (mínimo 12 caracteres): ")
        if password != read_secret("Repite la contraseña: "):
            print("Las contraseñas no coinciden. No se guardó ningún cambio.")
            return 1
        database = create_database_engine(url)
        identifier = create_initial_general_admin(database, email=email, password=password)
        print(f"Administrador general listo. ID: {identifier}. Correo: {email}.")
        print("Si la cuenta ya existía, conserva su contraseña. Las cuentas de negocio anteriores se conservan.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nAlta cancelada.")
        return 130
    except GetPassWarning:
        print("No se pudo ocultar la entrada; usa una terminal interactiva.")
        return 2
    except (ValueError, SQLAlchemyError):
        print("No se confirmó el alta. Revisa el correo, la conexión y si ya existe una cuenta de administración general.")
        return 1
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
