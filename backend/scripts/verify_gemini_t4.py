"""Comprueba el servicio de clasificación con Gemini y una base temporal sintética."""

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.core.ai_config import AISettings  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.repositories.review_repository import ReviewRepository  # noqa: E402
from app.schemas.review import ReviewRead  # noqa: E402
from app.services.ai_provider import AIError, create_ai_provider  # noqa: E402
from app.services.classification_service import (  # noqa: E402
    CLASSIFICATION_INSTRUCTIONS, ClassificationService, ClassificationContentError,
)


CASES = [
    ("queja", "Mi pedido llegó tarde y nadie resolvió el problema.", "Queja"),
    ("sugerencia", "Sería útil ofrecer entregas los domingos.", "Sugerencia"),
    ("felicitacion", "Excelente atención, gracias al equipo por su ayuda.", "Felicitación"),
    ("consulta", "¿Cuál es el horario de los sábados?", "Consulta"),
    ("mixta_queja", "Excelente comida, pero tardaron una hora.", "Queja"),
    ("sugerencia_en_pregunta", "¿Podrían abrir los domingos?", "Sugerencia"),
    ("no_analizable", "zxqv trplm qzxv", None),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Archivo nuevo de evidencia")
    args = parser.parse_args()
    now = datetime.now(ZoneInfo("America/Tijuana"))
    output = args.output or ROOT / f"docs/hu-13/evidencia-t4-{now:%Y%m%dT%H%M%S%f}.json"
    if output.exists():
        print("El archivo de evidencia ya existe; elige una ruta nueva.")
        return 2
    try:
        config = AISettings(_env_file=BACKEND / ".env")
    except ValidationError:
        print("La configuración de IA está ausente o no es válida.")
        return 2
    report = {
        "task": 3563, "timestamp": now.isoformat(), "model_requested": config.ai_model,
        "scope": "Servicio real y Gemini con reviews sintéticas en SQLite temporal; sin endpoint ni modificación de la base local",
        "instructions": CLASSIFICATION_INSTRUCTIONS, "planned": len(CASES), "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix="hu13-t4-") as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'verification.db'}")
        init_db(engine)
        with Session(engine) as db:
            db.add_all([Tenant(id=10, nombre="Prueba", estado="activo"),
                        Tenant(id=20, nombre="Ajeno", estado="activo")])
            db.flush()
            for review_id, (_, content, _) in enumerate(CASES, start=1):
                db.add(Review(
                    id=review_id, tenant_id=10, contenido=content,
                    fecha=now.replace(tzinfo=None), fuente="manual", puntuacion=3,
                    estado="en_revision", categoria="Consulta", prioridad="Alta",
                    resumen="Resumen conservado", tema="Tema conservado",
                ))
            db.add(Review(
                id=999, tenant_id=20, contenido="Reseña sintética de otro negocio",
                fecha=now.replace(tzinfo=None), fuente="manual", puntuacion=3,
                estado="nueva", categoria="Sugerencia",
            ))
            db.commit()
        try:
            for review_id, (name, content, expected) in enumerate(CASES, start=1):
                case = {"id": name, "input": content, "expected": expected}
                report["cases"].append(case)
                started = time.monotonic()
                with Session(engine) as db:
                    before = ReviewRead.model_validate(db.get(Review, review_id)).model_dump()
                    service = ClassificationService(ReviewRepository(db), lambda: create_ai_provider(config))
                    try:
                        saved = service.classify(review_id, 10)
                        case["category"] = saved.categoria
                        case["status"] = "passed" if expected is not None and saved.categoria == expected else "unexpected_category"
                    except ClassificationContentError as error:
                        case["error_code"] = error.code
                        case["status"] = "passed" if expected is None else "unexpected_rejection"
                    except AIError as error:
                        case["error_code"] = error.code
                        case["status"] = "failed"
                with Session(engine) as db:
                    after = ReviewRead.model_validate(db.get(Review, review_id)).model_dump()
                    case["persisted_category"] = after["categoria"]
                    case["other_fields_preserved"] = all(
                        after[field] == value for field, value in before.items() if field != "categoria"
                    )
                    case["previous_category_preserved_on_rejection"] = (
                        after["categoria"] == before["categoria"] if "error_code" in case else None
                    )
                    case["foreign_review_preserved"] = db.get(Review, 999).categoria == "Sugerencia"
                    if (not case["other_fields_preserved"] or not case["foreign_review_preserved"]
                        or case["previous_category_preserved_on_rejection"] is False):
                        case["status"] = "persistence_mismatch"
                case["elapsed_seconds"] = round(time.monotonic() - started, 3)
                print(f"{name}: {case['status']}")
                if case["status"] == "failed":
                    break
        finally:
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
