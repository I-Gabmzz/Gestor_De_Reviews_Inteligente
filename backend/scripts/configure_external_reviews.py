"""Configuración manual de una conexión Google; no consulta ni importa reseñas."""

import argparse
from getpass import GetPassWarning
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import create_database_engine
from app.services.external_connection_admin_service import configure_connection
from scripts.create_business import external_database_url, read_secret



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
