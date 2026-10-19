"""Verifica autenticación, aislamiento y clasificación HTTP con Gemini y SQLite temporal."""

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
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.api.dependencies import get_db  # noqa: E402
from app.core.ai_config import AISettings  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.review import ReviewRead  # noqa: E402
from app.services.ai_provider import create_ai_provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Archivo nuevo de evidencia")
    args = parser.parse_args()
    now = datetime.now(ZoneInfo("America/Tijuana"))
    output = args.output or ROOT / f"docs/hu-13/evidencia-t5-{now:%Y%m%dT%H%M%S%f}.json"
    if output.exists():
        print("El archivo de evidencia ya existe; elige una ruta nueva.")
        return 2
    try:
        config = AISettings(_env_file=BACKEND / ".env")
    except ValidationError:
        print("La configuración de IA está ausente o no es válida.")
        return 2
    report = {
        "task": 3564, "timestamp": now.isoformat(), "model_requested": config.ai_model,
        "scope": "Peticiones HTTP por TestClient con autenticación, servicio y Gemini reales; SQLite temporal con datos sintéticos; base local intacta",
        "endpoint": "POST /api/v1/reviews/{review_id}/clasificacion", "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix="hu13-t5-") as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'api.db'}", connect_args={"check_same_thread": False})
        sessions = sessionmaker(bind=engine)
        init_db(engine)
        password = secrets.token_urlsafe(24)
        with Session(engine) as db:
            db.add_all([Tenant(id=10, nombre="Prueba", estado="activo"),
                        Tenant(id=20, nombre="Ajeno", estado="activo")])
            db.flush()
            hashed = get_password_hash(password)
            for user_id, role, tenant_id in ((1, "usuario_negocio", 10), (2, "admin_tenant", 10), (3, "admin_general", None)):
                db.add(User(id=user_id, nombre="Cuenta sintética", correo=f"user{user_id}@example.com",
                            password_hash=hashed, rol=role, tenant_id=tenant_id, estado="activo"))
            for review_id, tenant_id in ((101, 10), (201, 20)):
                db.add(Review(
                    id=review_id, tenant_id=tenant_id, contenido="Mi pedido llegó tarde y nadie resolvió el problema.",
                    fecha=now.replace(tzinfo=None), fuente="manual", puntuacion=2,
                    estado="en_revision", categoria="Consulta", prioridad="Alta",
                    resumen="Resumen conservado", tema="Entrega",
                ))
            db.commit()

        def override_db():
            with sessions() as db:
                yield db

        calls = 0
        def provider_factory():
            nonlocal calls
            calls += 1
            return create_ai_provider(config)

        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_db
        try:
            with patch("app.main.init_db", lambda: init_db(engine)), patch(
                "app.services.classification_service.create_ai_provider", provider_factory
            ), TestClient(app) as client:
                headers = {}
                for user_id in (1, 2, 3):
                    login = client.post("/api/v1/auth/login", json={
                        "correo": f"user{user_id}@example.com", "password": password
                    })
                    if login.status_code != 200:
                        print("Falló la preparación de autenticación sintética.")
                        return 1
                    headers[user_id] = {"Authorization": f"Bearer {login.json()['access_token']}"}

                cases = [
                    ("sin_token", 101, None, None, 401, False),
                    ("admin_general", 101, 3, None, 403, False),
                    ("review_ajena", 201, 1, None, 404, False),
                    ("review_inexistente", 999, 1, None, 404, False),
                    ("cuerpo_no_editable", 101, 1, {"tenant_id": 20, "categoria": "Felicitación"}, 422, False),
                    ("usuario_negocio", 101, 1, None, 200, True),
                    ("admin_tenant", 101, 2, None, 200, True),
                ]
                report["planned"] = len(cases) + 1
                for name, review_id, user_id, payload, expected, should_call in cases:
                    with sessions() as db:
                        before = ReviewRead.model_validate(db.get(Review, 101)).model_dump(mode="json")
                    count_before = calls
                    response = client.post(f"/api/v1/reviews/{review_id}/clasificacion",
                                           headers=headers.get(user_id, {}), json=payload)
                    case = {"id": name, "http_status": response.status_code, "expected_status": expected,
                            "provider_calls": calls - count_before}
                    with sessions() as db:
                        after = ReviewRead.model_validate(db.get(Review, 101)).model_dump(mode="json")
                        case["foreign_review_preserved"] = db.get(Review, 201).categoria == "Consulta"
                    expected_after = before | {"categoria": "Queja"} if expected == 200 else before
                    case["persisted_data_match"] = after == expected_after
                    if expected == 200 and response.status_code == 200:
                        case["category"] = response.json()["categoria"]
                        case["get_matches_post"] = client.get("/api/v1/reviews/101", headers=headers[user_id]).json() == response.json() == after
                    case["status"] = "passed" if (
                        response.status_code == expected and calls - count_before == int(should_call)
                        and case["persisted_data_match"] and case["foreign_review_preserved"]
                        and case.get("get_matches_post", True)
                    ) else "failed"
                    report["cases"].append(case)
                    print(f"{name}: {case['status']} (HTTP {response.status_code})")
                    if response.status_code >= 500:
                        break
                else:
                    with sessions() as db:
                        db.get(Tenant, 10).estado = "inactivo"
                        db.commit()
                    count_before = calls
                    denied = client.post("/api/v1/reviews/101/clasificacion", headers=headers[1])
                    report["cases"].append({"id": "tenant_inactivo_token_previo", "http_status": denied.status_code,
                        "expected_status": 403, "provider_calls": calls - count_before,
                        "status": "passed" if denied.status_code == 403 and calls == count_before else "failed"})
                    print(f"tenant_inactivo_token_previo: {report['cases'][-1]['status']}")
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
            engine.dispose()
    report["passed"] = sum(case["status"] == "passed" for case in report["cases"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as report_file:
        report_file.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Evidencia: {output}")
    print(f"Casos aprobados: {report['passed']}/{report['planned']}")
    return 0 if report["passed"] == report["planned"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
