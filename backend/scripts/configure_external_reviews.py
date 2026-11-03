"""Configuración manual de una conexión Google; no consulta ni importa reseñas."""

import argparse
from getpass import GetPassWarning
import re
import sys

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.connection import create_database_engine
from app.models import ExternalReviewConnection, ExternalReviewImportAttempt, Tenant
from scripts.create_business import external_database_url, read_secret


def configure_connection(database: Engine, *, tenant_id: int, expected_name: str,
                         business_data_id: str, approval_reference: str) -> bool:
    """Devuelve True al crear; una conexión ya habilitada conserva su referencia."""
    if (type(tenant_id) is not int or tenant_id < 1 or not expected_name.strip()
            or len(expected_name) > 255 or len(business_data_id) > 128
            or re.fullmatch(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+", business_data_id) is None
            or not approval_reference.strip() or len(approval_reference) > 255):
        raise ValueError("Revisa el negocio, el identificador de Google y la referencia de aprobación")
    with Session(database) as db, db.begin():
        if database.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(32513563)"))
        elif database.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise ValueError("Motor de base de datos no soportado")
        tenant = db.get(Tenant, tenant_id)
        if tenant is None or tenant.nombre != expected_name or tenant.estado != "activo":
            raise ValueError("El ID y el nombre no corresponden a un negocio activo; no se modificó")
        pending = db.scalar(select(ExternalReviewImportAttempt.operation_id).where(
            ExternalReviewImportAttempt.tenant_id == tenant_id,
            ExternalReviewImportAttempt.active.is_(True),
        ))
        if pending is not None:
            raise ValueError("Hay una importación pendiente de revisión; no se modificó la conexión")
        connections = list(db.scalars(select(ExternalReviewConnection).where(
            ExternalReviewConnection.tenant_id == tenant_id,
            ExternalReviewConnection.source == "Google",
        )))
        if any(row.business_data_id != business_data_id for row in connections):
            raise ValueError("El negocio ya tiene otra conexión Google; revisa la configuración existente")
        configured = connections[0] if connections else None
        created = configured is None
        if created:
            configured = ExternalReviewConnection(tenant_id=tenant_id, source="Google",
                                                 business_data_id=business_data_id)
            db.add(configured)
        if not configured.persistence_enabled:
            configured.approval_reference = approval_reference.strip()
            configured.persistence_enabled = True
        return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configurar una conexión Google para un negocio existente")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--name", required=True, help="Nombre exacto del negocio existente")
    parser.add_argument("--data-id", required=True, help="Identificador público de Google Maps")
    parser.add_argument("--approval", required=True, help="Referencia real de la aprobación de uso")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print("Usa una terminal interactiva para introducir la conexión en privado.")
        return 2
    database = None
    try:
        url = external_database_url(read_secret("External Database URL de Render (entrada oculta): "))
        print(f"Destino: {url.host} / {url.database}")
        print(f"Negocio ID {args.tenant_id}: {args.name} | Google: {args.data_id}")
        print(f"Referencia: {args.approval}")
        if input("Escribe CONFIGURAR para habilitar esta conexión: ").strip() != "CONFIGURAR":
            print("Configuración cancelada.")
            return 0
        database = create_database_engine(url)
        created = configure_connection(database, tenant_id=args.tenant_id, expected_name=args.name,
                                       business_data_id=args.data_id, approval_reference=args.approval)
        print("Conexión creada y habilitada." if created else "Conexión existente verificada y habilitada.")
        print("No se consultó SerpApi ni se importaron reseñas. El servidor requiere su habilitación independiente.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nConfiguración cancelada.")
        return 130
    except GetPassWarning:
        print("No se pudo ocultar la entrada; usa una terminal interactiva.")
        return 2
    except ValueError as error:
        # Sólo mensajes fijos de los validadores propios; no serializar entradas.
        print(f"No se completó la configuración: {error}")
        return 1
    except SQLAlchemyError:
        print("No se confirmó la configuración. Revisa la conexión y vuelve a verificar antes de importar.")
        return 1
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
