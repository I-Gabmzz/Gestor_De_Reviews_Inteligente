"""Router de importación de archivos.

TASK 3316: Endpoint para la carga de archivos CSV y Excel.
TASK 3317: Endpoint para la validación del formato del archivo importado.
TASK 3318: Procesamiento y almacenamiento de reviews importadas.

Expone:
    POST /api/v1/imports/upload
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_tenant_id, get_db
from app.services.import_service import (
    ALLOWED_EXTENSIONS,
    process_and_store_import,
)

router = APIRouter(prefix="/imports", tags=["imports"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentTenantId = Annotated[int, Depends(get_current_tenant_id)]
UploadedReviewFile = Annotated[
    UploadFile,
    File(..., description="Archivo CSV o Excel (.xlsx) con reviews"),
]


async def import_reviews_for_tenant(
    file: UploadFile,
    tenant_id: int,
    db: Session,
) -> dict:
    """Valida y persiste un archivo de reviews usando el tenant autenticado."""
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


@router.post("/upload")
async def upload_file(
    file: UploadedReviewFile,
    tenant_id: CurrentTenantId,
    db: DatabaseSession,
) -> dict:
    """Recibe un archivo CSV o Excel y persiste las reviews en el tenant autenticado."""
    return await import_reviews_for_tenant(file=file, tenant_id=tenant_id, db=db)
