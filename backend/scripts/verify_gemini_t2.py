"""Comprueba el adaptador común con tres operaciones sintéticas, sin persistencia."""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, ValidationError


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.core.ai_config import AISettings  # noqa: E402
from app.schemas.ai import AIResponse  # noqa: E402
from app.services.ai_provider import AIError, create_ai_provider  # noqa: E402


class ClassificationProbe(AIResponse):
    categoria: Literal["Queja", "Sugerencia", "Felicitación", "Consulta"]


class SummaryProbe(AIResponse):
    resumen: str = Field(min_length=1)


class TopicProbe(AIResponse):
    tema: str = Field(min_length=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Archivo nuevo de evidencia")
    args = parser.parse_args()
    now = datetime.now(ZoneInfo("America/Tijuana"))
    output_path = args.output or ROOT / f"docs/hu-13/evidencia-t2-{now:%Y%m%dT%H%M%S%f}.json"
    if output_path.exists():
        print("El archivo de evidencia ya existe; elige una ruta nueva.")
        return 2
    content = "Mi pedido llegó una hora tarde y la comida estaba fría."
    cases = [
        ("clasificacion", ClassificationProbe, "Clasifica la intención principal en Queja, Sugerencia, Felicitación o Consulta."),
        ("resumen", SummaryProbe, "Resume la reseña en español en una frase, conservando los hechos sin inventar información."),
        ("tema", TopicProbe, "Identifica el tema principal de la reseña en una etiqueta breve en español."),
    ]
    report = {
        "task": 3561,
        "timestamp": now.isoformat(),
        "scope": "Comprobación real del adaptador compartido, sin endpoints ni persistencia; resumen y tema son pruebas de transporte, no aceptación de HU-14/HU-15",
        "input": content,
        "cases": [],
        "planned": len(cases),
    }
    try:
        config = AISettings(_env_file=BACKEND / ".env")
    except ValidationError:
        print("La configuración de IA está ausente o no es válida.")
        return 2
    report["provider"] = config.ai_provider
    report["model_requested"] = config.ai_model
    with create_ai_provider(config) as provider:
        for operation, response_model, instructions in cases:
            started = time.monotonic()
            case = {"operation": operation, "schema": response_model.model_json_schema()}
            report["cases"].append(case)
            try:
                result = provider.generate_structured(
                    content, instructions=instructions, response_model=response_model
                )
                case["output"] = result.model_dump()
                case["valid_schema"] = True
                case["status"] = "passed"
                if operation == "clasificacion" and result.categoria != "Queja":
                    case["status"] = "unexpected_category"
                print(f"{operation}: {case['status']}")
            except AIError as exc:
                case["status"] = "failed"
                case["error_code"] = exc.code
                print(f"{operation}: error controlado ({exc.code})")
                break
            finally:
                case["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["passed"] = sum(case["status"] == "passed" for case in report["cases"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output_file:
        output_file.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Evidencia: {output_path}")
    print(f"Operaciones aprobadas: {report['passed']}/{report['planned']}")
    return 0 if report["passed"] == report["planned"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
