"""Comprueba HU-20 con Gemini real y reseñas sintéticas en una base temporal."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import secrets
import sys
import tempfile
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.api.dependencies import get_db  # noqa: E402
from app.core.ai_config import AISettings  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.notification import ReviewNotification  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.ai_provider import create_ai_provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Archivo nuevo para el resultado")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("El resultado ya existe; usa otro nombre para conservarlo.")
    settings = AISettings(_env_file=BACKEND / ".env")
    report = {"task": 3830, "timestamp": datetime.now(ZoneInfo("America/Tijuana")).isoformat(),
              "provider": "Google Gemini Developer API", "model_requested": settings.ai_model,
              "scope": "HTTP por TestClient, proveedor real y SQLite temporal; solo reseñas sintéticas",
              "cases": [], "provider_calls": 0}

    def provider():
        report["provider_calls"] += 1
        return create_ai_provider(settings)

    def check(name, passed, **data):
        report["cases"].append({"id": name, "passed": bool(passed), **data})
        print(f"{name}: {'passed' if passed else 'failed'}", flush=True)

    with tempfile.TemporaryDirectory(prefix="hu20-t5-") as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'notifications.db'}", connect_args={"check_same_thread": False})
        sessions = sessionmaker(bind=engine)
        init_db(engine)
        password = secrets.token_urlsafe(24)
        with Session(engine) as db:
            db.add_all([Tenant(id=10, nombre="Negocio sintético A", estado="activo"),
                        Tenant(id=20, nombre="Negocio sintético B", estado="activo")])
            db.flush()
            hashed = get_password_hash(password)
            for user_id, tenant, role in ((1, 10, "usuario_negocio"), (2, 10, "admin_tenant"),
                                           (3, 20, "usuario_negocio"), (4, None, "admin_general")):
                db.add(User(id=user_id, tenant_id=tenant, rol=role, nombre="Cuenta sintética",
                            correo=f"case{user_id}@example.com", password_hash=hashed, estado="activo"))
            for review_id, tenant, content in (
                (101, 10, "Me cobraron dos veces y nadie me responde."),
                (102, 10, "¿Cuál es el horario de los sábados?"),
                (201, 20, "Review sintética del segundo negocio."),
            ):
                db.add(Review(id=review_id, tenant_id=tenant, autor="Cliente sintético", contenido=content,
                              fecha=datetime(2026, 11, 2), fuente="manual", puntuacion=5,
                              estado="en_revision", prioridad="Media", categoria="Consulta",
                              resumen="Resumen conservado", tema="Tema conservado"))
            db.commit()

        def database():
            with sessions() as db:
                yield db

        previous = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = database
        try:
            with patch("app.main.init_db", lambda: init_db(engine)), patch(
                "app.services.priority_service.create_ai_provider", provider
            ), TestClient(app) as client:
                headers = {}
                for user_id in (1, 2, 3, 4):
                    result = client.post("/api/v1/auth/login", json={"correo": f"case{user_id}@example.com", "password": password})
                    result.raise_for_status()
                    headers[user_id] = {"Authorization": f"Bearer {result.json()['access_token']}"}

                url = "/api/v1/reviews/101"
                before = client.get(url, headers=headers[1]).json()
                result = client.post(url + "/prioridad", headers=headers[1])
                notices = client.get("/api/v1/notificaciones", headers=headers[1]).json()
                check("alta_genera_aviso", result.status_code == 200 and result.json() == before | {"prioridad": "Alta"}
                      and notices["total"] == 1 and notices["items"][0]["review_id"] == 101,
                      http_status=result.status_code, prioridad=result.json().get("prioridad"), total=notices["total"])
                shared = client.get("/api/v1/notificaciones", headers=headers[2]).json()
                check("administrador_comparte_aviso", shared == notices)
                retry = client.post(url + "/prioridad", headers=headers[2])
                reloaded = client.get("/api/v1/notificaciones", headers=headers[1]).json()
                check("reintento_conserva_aviso_y_fecha", retry.status_code == 200 and retry.json().get("prioridad") == "Alta"
                      and reloaded == notices, http_status=retry.status_code)
                low = client.post("/api/v1/reviews/102/prioridad", headers=headers[1])
                check("no_alta_sin_aviso", low.status_code == 200 and low.json().get("prioridad") == "Baja"
                      and client.get("/api/v1/notificaciones", headers=headers[1]).json() == notices,
                      http_status=low.status_code, prioridad=low.json().get("prioridad"))
                read = client.get(url, headers=headers[1])
                check("lectura_conserva_seguimiento", read.status_code == 200 and read.json() == before | {"prioridad": "Alta"})
                foreign = client.get("/api/v1/notificaciones?tenant_id=10", headers=headers[3])
                link = client.get(url, headers=headers[3])
                check("otro_negocio_sin_aviso_ni_detalle", foreign.status_code == 200
                      and foreign.json() == {"items": [], "total": 0} and link.status_code == 404)
                check("administrador_general_sin_acceso", client.get("/api/v1/notificaciones", headers=headers[4]).status_code == 403)
                check("sin_sesion_sin_acceso", client.get("/api/v1/notificaciones").status_code == 401)
                with Session(engine) as db:
                    check("un_solo_evento_persistido", db.query(ReviewNotification).count() == 1
                          and db.get(Review, 102).estado == "en_revision" and db.get(Review, 201).prioridad == "Media")
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)
            engine.dispose()

    report["passed"] = all(case["passed"] for case in report["cases"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
