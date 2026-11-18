"""Entorno local efímero para validación manual de HU-24; no usa proveedores externos."""
import os
from pathlib import Path
import secrets
import tempfile


def main():
    # La ubicación la genera Python, no la suministra el usuario ni se reutiliza.
    with tempfile.TemporaryDirectory(prefix='hu24-t6-e2e-') as directory:
        root = Path(directory).resolve(strict=True)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
        database = root / 'synthetic.sqlite'
        if root.parent != temp_root or not root.name.startswith('hu24-t6-e2e-') or database.exists():
            raise RuntimeError('No se pudo verificar una base temporal nueva')
        expected_url = f"sqlite:///{database.as_posix()}"
        os.environ['DATABASE_URL'] = expected_url
        os.environ['HU24_ALLOW_REVIEW_NULLABLE_MIGRATION'] = 'false'
        os.environ['EXTERNAL_IMPORT_ENABLED'] = 'false'
        os.environ['SECRET_KEY'] = secrets.token_urlsafe(48)
        for name in ('SERPAPI_API_KEY', 'GEMINI_API_KEY', 'TEST_POSTGRES_URL'):
            os.environ.pop(name, None)

        # Importar la aplicación solo después de fijar y comprobar la URL.
        from app.core.config import settings
        if settings.database_url != expected_url:
            raise RuntimeError('La URL de la base no coincide con la base temporal')
        from app.core.security import get_password_hash
        from app.db.connection import SessionLocal, engine
        from app.db.init_db import init_db
        from app.main import app
        from app.models import Tenant, User
        import uvicorn

        init_db(engine)
        password = secrets.token_urlsafe(18)
        with SessionLocal() as db:
            db.add_all([Tenant(id=10, nombre='T6 A', estado='activo'), Tenant(id=20, nombre='T6 B', estado='activo')])
            db.flush()
            for tenant in (10, 20):
                db.add(User(tenant_id=tenant, nombre=f'T6 {tenant}', correo=f't6-{tenant}@example.com',
                            password_hash=get_password_hash(password), rol='usuario_negocio', estado='activo'))
            db.commit()
        print(f'Base temporal verificada: {database}', flush=True)
        print(f'Usuarios sintéticos: t6-10@example.com y t6-20@example.com; contraseña temporal: {password}', flush=True)
        print('Backend temporal en http://127.0.0.1:8000; Ctrl+C para terminar.', flush=True)
        try:
            uvicorn.run(app, host='127.0.0.1', port=8000, log_level='warning')
        finally:
            engine.dispose()


if __name__ == '__main__':
    main()
