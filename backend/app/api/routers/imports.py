"""Router de importación de archivos.

TASK 3316: Endpoint para la carga de archivos CSV y Excel.
TASK 3317: Endpoint para la validación del formato del archivo importado.

Expone:
    POST /api/v1/imports/upload
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.import_service import ALLOWED_EXTENSIONS, parse_file, validate_import

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="Archivo CSV o Excel (.xlsx) con reviews"),
) -> dict:
    """Recibe un archivo CSV o Excel, parsea sus filas y valida su formato.

    Aplica las reglas de TASK 3316 (parseo) y TASK 3317 (validación):
    - Comprueba extensión del archivo.
    - Valida que el archivo no esté vacío.
    - Valida presencia de encabezados obligatorios ('contenido', 'fecha', 'puntuacion').
    - Valida reglas de tipo, rango y formato por cada fila.

    Args:
        file: Archivo subido por el usuario (multipart/form-data).

    Returns:
        Diccionario con el resumen del informe de validación y lista de errores por fila.

    Raises:
        HTTPException 400: Si la extensión no es soportada o el archivo no se puede leer.
    """
    filename = file.filename or ""
    extension = filename[filename.rfind("."):].lower() if "." in filename else ""

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Formato de archivo no soportado: '{extension}'. "
                f"Extensiones permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Error al leer el archivo: {exc}",
        )
    finally:
        await file.close()

    try:
        rows = parse_file(file_bytes, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Ejecutar validaciones de TASK 3317
    validation_result = validate_import(rows)

    # Excluir 'datos_validos' de la respuesta HTTP final para no inflar la respuesta
    return {
        "filename": filename,
        "es_valido": validation_result["es_valido"],
        "total_filas": validation_result["total_filas"],
        "filas_validas": validation_result["filas_validas"],
        "total_errores": validation_result["total_errores"],
        "errores_globales": validation_result["errores_globales"],
        "errores_por_fila": validation_result["errores_por_fila"],
    }
