"""Servicio de importación de archivos CSV y Excel.

TASK 3316: Carga y lectura de archivos CSV y Excel.
TASK 3317: Validación del formato del archivo importado con soporte de aliases de encabezados.

Responsabilidades:
- Detectar el formato del archivo por extensión.
- Leer el contenido binario del archivo a lista de diccionarios.
- Validar archivo vacío y presencia de encabezados obligatorios ('contenido', 'fecha', 'puntuacion') soportando aliases canónicos.
- Validar tipo, rango y formato de datos por fila (contenido no vacío, puntuación 1-5, fecha válida).
- Reportar errores globales y detallados por fila.
"""

import csv
from datetime import date, datetime
import io
import re
from typing import Any

from openpyxl import load_workbook


ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
REQUIRED_HEADERS = {"contenido", "fecha", "puntuacion"}

# Mapeo de nombres canónicos a sus variantes / aliases permitidos
HEADER_ALIASES = {
    "contenido": {"contenido", "reseña", "resena", "review"},
    "puntuacion": {"puntuacion", "score", "estrellas", "calificacion"},
    "fecha": {"fecha", "date"},
}


def parse_file(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Lee un archivo CSV o Excel y retorna su contenido como lista de diccionarios.

    Cada diccionario representa una fila del archivo, donde las claves
    son los nombres de las columnas del encabezado.

    Args:
        file_bytes: Contenido binario del archivo.
        filename: Nombre original del archivo (se usa para detectar la extensión).

    Returns:
        Lista de diccionarios con los datos de cada fila.

    Raises:
        ValueError: Si la extensión del archivo no es soportada.
    """
    extension = _get_extension(filename)

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Formato de archivo no soportado: '{extension}'. "
            f"Extensiones permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if extension == ".csv":
        return _parse_csv(file_bytes)

    return _parse_xlsx(file_bytes)


def validate_import(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Valida el contenido importado respetando las reglas de TASK 3317.

    Comprueba:
    1. Que el archivo no esté vacío.
    2. Presencia de encabezados obligatorios ('contenido', 'fecha', 'puntuacion') usando aliases canónicos.
    3. Para cada fila: contenido no vacío, puntuación entre 1 y 5, fecha parseable.

    Args:
        rows: Lista de diccionarios obtenida de parse_file().

    Returns:
        Diccionario con el resultado de la validación:
        - es_valido: bool
        - total_filas: int
        - filas_validas: int
        - total_errores: int
        - errores_globales: list[str]
        - errores_por_fila: list[dict]
        - datos_validos: list[dict] (Conservado en memoria para TASK 3318)
    """
    if not rows:
        return {
            "es_valido": False,
            "total_filas": 0,
            "filas_validas": 0,
            "total_errores": 1,
            "errores_globales": ["El archivo está vacío o no contiene filas de datos."],
            "errores_por_fila": [],
            "datos_validos": [],
        }

    # Normalizar y canonizar llaves del primer registro para verificar encabezados
    raw_headers = list(rows[0].keys())
    header_map = {_normalize_header(h): h for h in raw_headers if h is not None}
    present_headers = set(header_map.keys())

    missing_headers = sorted(REQUIRED_HEADERS - present_headers)
    if missing_headers:
        return {
            "es_valido": False,
            "total_filas": len(rows),
            "filas_validas": 0,
            "total_errores": len(missing_headers),
            "errores_globales": [
                f"Faltan los siguientes encabezados obligatorios: {', '.join(missing_headers)}"
            ],
            "errores_por_fila": [],
            "datos_validos": [],
        }

    datos_validos: list[dict[str, Any]] = []
    errores_por_fila: list[dict[str, Any]] = []

    for index, raw_row in enumerate(rows, start=1):
        # Mapear llaves de la fila a los encabezados canónicos normalizados
        normalized_row = {
            _normalize_header(k): v for k, v in raw_row.items() if k is not None
        }

        row_errors = _validate_row(normalized_row, index)

        if row_errors:
            errores_por_fila.extend(row_errors)
        else:
            # Conservar fila válida para uso posterior (TASK 3318)
            datos_validos.append(normalized_row)

    es_valido = len(errores_por_fila) == 0

    return {
        "es_valido": es_valido,
        "total_filas": len(rows),
        "filas_validas": len(datos_validos),
        "total_errores": len(errores_por_fila),
        "errores_globales": [],
        "errores_por_fila": errores_por_fila,
        "datos_validos": datos_validos,
    }


def _get_extension(filename: str) -> str:
    """Extrae la extensión del nombre de archivo en minúsculas."""
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return ""
    return filename[dot_index:].lower()


def _normalize_header(header: str) -> str:
    """Normaliza un nombre de encabezado a su forma canónica.

    Aplica minúsculas, remueve espacios y tildes, y si la palabra coincide
    con alguna variante/alias conocida la convierte al nombre canónico oficial.
    """
    if not isinstance(header, str):
        header = str(header)

    cleaned = header.strip().lower()
    cleaned = re.sub(r"[áäâà]", "a", cleaned)
    cleaned = re.sub(r"[éëêè]", "e", cleaned)
    cleaned = re.sub(r"[íïîì]", "i", cleaned)
    cleaned = re.sub(r"[óöôò]", "o", cleaned)
    cleaned = re.sub(r"[úüûù]", "u", cleaned)

    for canonical, aliases in HEADER_ALIASES.items():
        if cleaned in aliases:
            return canonical

    return cleaned


def _parse_csv(file_bytes: bytes) -> list[dict[str, Any]]:
    """Parsea un archivo CSV desde sus bytes."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _parse_xlsx(file_bytes: bytes) -> list[dict[str, Any]]:
    """Parsea un archivo Excel (.xlsx) desde sus bytes."""
    workbook = load_workbook(filename=io.BytesIO(file_bytes), read_only=True)
    sheet = workbook.active

    rows = list(sheet.iter_rows(values_only=True))
    workbook.close()

    if len(rows) < 1:
        return []

    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]

    data: list[dict[str, Any]] = []
    for row in rows[1:]:
        row_dict: dict[str, Any] = {}
        for header, cell in zip(headers, row):
            row_dict[header] = cell
        data.append(row_dict)

    return data


def _validate_row(row: dict[str, Any], row_num: int) -> list[dict[str, Any]]:
    """Valida los campos de una fila individual.

    Args:
        row: Diccionario con llaves canónicas ('contenido', 'fecha', 'puntuacion').
        row_num: Número de fila (1-indexed).

    Returns:
        Lista de diccionarios de error para la fila. Si está limpia, retorna [].
    """
    errors: list[dict[str, Any]] = []

    # 1. Validación de contenido
    contenido_raw = row.get("contenido")
    if contenido_raw is None or str(contenido_raw).strip() == "":
        errors.append({
            "fila": row_num,
            "campo": "contenido",
            "valor_recibido": contenido_raw,
            "mensaje": "El campo 'contenido' no puede estar vacío.",
        })

    # 2. Validación de puntuacion
    puntuacion_raw = row.get("puntuacion")
    score_ok, score_error_msg = _validate_score(puntuacion_raw)
    if not score_ok:
        errors.append({
            "fila": row_num,
            "campo": "puntuacion",
            "valor_recibido": puntuacion_raw,
            "mensaje": score_error_msg,
        })

    # 3. Validación de fecha
    fecha_raw = row.get("fecha")
    date_ok, date_error_msg = _validate_date(fecha_raw)
    if not date_ok:
        errors.append({
            "fila": row_num,
            "campo": "fecha",
            "valor_recibido": fecha_raw,
            "mensaje": date_error_msg,
        })

    return errors


def _validate_score(score_val: Any) -> tuple[bool, str]:
    """Valida que la puntuación sea un entero entre 1 y 5."""
    if score_val is None or str(score_val).strip() == "":
        return False, "La puntuación es obligatoria y no puede estar vacía."

    try:
        score_float = float(score_val)
        if not score_float.is_integer():
            return False, f"La puntuación debe ser un número entero sin decimales (recibido: '{score_val}')."
        score_int = int(score_float)
    except (ValueError, TypeError):
        return False, f"La puntuación debe ser un valor numérico entero (recibido: '{score_val}')."

    if score_int < 1 or score_int > 5:
        return False, f"La puntuación debe estar entre 1 y 5 (recibido: '{score_int}')."

    return True, ""


def _validate_date(date_val: Any) -> tuple[bool, str]:
    """Valida que la fecha sea parseable a un objeto de fecha válido."""
    if date_val is None or str(date_val).strip() == "":
        return False, "La fecha es obligatoria y no puede estar vacía."

    if isinstance(date_val, (datetime, date)):
        return True, ""

    date_str = str(date_val).strip()

    date_formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d",
    ]

    for fmt in date_formats:
        try:
            datetime.strptime(date_str, fmt)
            return True, ""
        except ValueError:
            continue

    # Intento con ISO fromisoformat
    try:
        datetime.fromisoformat(date_str)
        return True, ""
    except ValueError:
        pass

    return (
        False,
        f"Formato de fecha no reconocido: '{date_val}'. Formatos soportados: YYYY-MM-DD, DD/MM/YYYY, ISO 8601.",
    )
