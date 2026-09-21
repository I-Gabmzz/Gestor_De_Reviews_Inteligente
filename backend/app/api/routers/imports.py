"""Router de importación de archivos.

TASK 3316: Endpoint para la carga de archivos CSV y Excel.

Expone:
    POST /api/v1/imports/upload
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.import_service import ALLOWED_EXTENSIONS, parse_file

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="Archivo CSV o Excel (.xlsx) con reviews"),
) -> dict:
    """Recibe un archivo CSV o Excel y retorna su contenido parseado.

    El archivo se lee completo en memoria, se delega al ImportService
    para su parseo y se retorna la lista de filas como diccionarios.

    Args:
        file: Archivo subido por el usuario (multipart/form-data).

    Returns:
        Diccionario con el nombre del archivo, cantidad de filas y los datos.

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

    return {
        "filename": filename,
        "total_filas": len(rows),
        "filas": rows,
    }
