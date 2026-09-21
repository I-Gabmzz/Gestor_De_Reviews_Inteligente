"""Router de importación de archivos.

TASK 3316: Endpoint para la carga de archivos CSV y Excel.
TASK 3317: Endpoint para la validación del formato del archivo importado.
TASK 3318: Procesamiento y almacenamiento de reviews importadas.

Expone:
    POST /api/v1/imports/upload
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.services.import_service import (
    ALLOWED_EXTENSIONS,
    process_and_store_import,
)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="Archivo CSV o Excel (.xlsx) con reviews"),
    tenant_id: int = Query(1, description="ID del tenant destino"),
    db: Session = Depends(get_db),
) -> dict:
    """Recibe un archivo CSV o Excel, lo valida y persiste las reviews en base de datos.

    Aplica las reglas de:
    - TASK 3316 (carga y parseo)
    - TASK 3317 (validación de formato y estructura)
    - TASK 3318 (transformación y persistencia transaccional mediante ReviewRepository)

    Args:
        file: Archivo subido por el usuario (multipart/form-data).
        tenant_id: ID del tenant destino (inyectado desde el contexto).
        db: Sesión de base de datos SQLAlchemy (Depends).

    Returns:
        Diccionario con el resumen del informe de importación y la cantidad de filas guardadas.

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
        result = process_and_store_import(
            file_bytes=file_bytes,
            filename=filename,
            tenant_id=tenant_id,
            db=db,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error transaccional al procesar la importación: {exc}",
        )
