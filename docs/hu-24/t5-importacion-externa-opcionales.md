# HU-24 / T5 — Reseñas externas con datos opcionales

## Actualización de validación — 2026-11-17

Sobre el candidato `1ecd9cde4a0a09fb71402ecaedc89a090e09f13c`, la validación de Google/SerpApi **real permanece BLOCKED**. No se identificaron una conexión real y un tenant de pruebas expresamente autorizados ni disponibilidad acreditada de credenciales para esa prueba. No se consultaron ni modificaron bases compartidas, no se creó una conexión y no se hicieron llamadas reales. Se requiere identificar y autorizar el tenant, la conexión, las credenciales y el presupuesto antes de ejecutar una importación real y repetirla para comprobar deduplicación. Las pruebas simuladas documentadas abajo conservan su alcance y no acreditan al proveedor real. El manejo de fallos simulados no se repitió en esta sesión.

Actualización posterior: el PO autorizó utilizar una conexión existente y un tenant de pruebas, pero todavía no se identificaron inequívocamente el tenant, la conexión, el acceso seguro al entorno ni el presupuesto máximo. La autorización general no identifica esos recursos. No se realizó ninguna llamada real. La política predeterminada reserva una solicitud por importación y permite una por tenant en una ventana de una hora; la configuración real y el presupuesto autorizado deben confirmarse antes de planificar las dos importaciones. Una reserva no equivale necesariamente a un crédito facturado.

Estado histórico al redactar la evidencia original: implementación local pendiente de auditoría y sin publicación. Posteriormente se publicó y se integró; la validación real pendiente se describe arriba. Esta tarea adapta el flujo Google/SerpApi de HU-21 al contrato de HU-24 y no cambia CSV/Excel ni el frontend.

## Alcance y reglas

Antes, el normalizador y la persistencia exigían fecha y puntuación aun cuando el modelo de T2 ya permitía NULL. Ahora un campo `iso_date` o `rating` omitido o explícitamente `null` se normaliza a `None` y se guarda como SQL NULL. Autor ausente conserva su tratamiento anterior. Una cadena de fecha vacía o blanca se rechaza como valor presente inválido; puntuaciones de texto, booleanos, fracciones y valores fuera de 1 a 5 siguen rechazándose. Las fechas presentes válidas conservan la normalización a UTC. No se inventan datos.

Las reseñas sin contenido continúan en la categoría omitida, sin insertar Review ni identidad externa. Se conservan la verificación de procedencia Google, los controles de usuario, tenant y conexión, las reglas de adquisición incompleta y los controles transaccionales y de commit incierto de HU-21. Reimportar una identidad existente distingue huella idéntica de cambio y no sobrescribe la reseña.

## Huellas y persistencia

El DTO interno y la validación defensiva admiten fecha y puntuación nulas; la fecha solo se transforma a UTC sin zona para el modelo cuando existe. La huella `v1` conserva exactamente la serialización previa para registros completos. Para ausencias se usa `null` de JSON en la posición correspondiente, que no se confunde con la fecha ISO ni con puntuaciones numéricas. Se conserva el algoritmo y la versión, sin migrar identidades ni reescribir registros históricos.

Una prueba fija la huella histórica sintética `v1:75c508d644e8db79264d2b6e45933e6a3cda50e252988fe402c4af6713858151`, compara reimportaciones y verifica distintas combinaciones de nulos. No se requiere migración nueva: una base existente debe tener aplicada y verificada la migración T2 antes de utilizar estos campos.

## Archivos

- `backend/app/schemas/external_review.py`: DTO interno con fecha y puntuación opcionales.
- `backend/app/services/serpapi_normalizer.py`: normalización de ausencias y validaciones existentes para valores presentes.
- `backend/app/services/external_review_persistence_service.py`: validación defensiva, huella y escritura compatibles con nulos.
- `backend/tests/unit/test_serpapi_normalizer.py`: casos de ausencia y entradas inválidas.
- `backend/tests/test_external_review_persistence.py`: huella histórica, reimportación, tenants y rollback con nulos.
- `backend/tests/test_external_review_import_api.py`: importación HTTP y lectura con proveedores simulados y dos tenants.
- `docs/hu-24/t5-importacion-externa-opcionales.md`: esta evidencia.

## Pruebas ejecutadas

Desde `backend/`, Python del entorno virtual existente del Sprint 3, `DATABASE_URL=sqlite://`, bases SQLite temporales, proveedores simulados y sin credenciales reales:

```text
python -m pytest tests/unit/test_serpapi_normalizer.py tests/test_external_review_persistence.py tests/test_external_review_import_api.py -k "t5 or optional_external" -q -p no:cacheprovider
15 passed, 310 deselected, 187 warnings in 2.17s
```

Antes de añadir la última prueba específica de rollback con nulos se ejecutó la regresión relacionada:

```text
python -m pytest tests/unit/test_serpapi_normalizer.py tests/unit/test_serpapi_client.py tests/test_external_review_persistence.py tests/test_external_review_import_api.py tests/test_external_review_integration.py tests/test_external_review_native_contract.py tests/test_hu24_nullable_migration.py tests/test_hu24_t3_optional_reviews.py tests/test_hu24_t4_import_export.py -q -p no:cacheprovider
595 passed, 2420 warnings in 44.34s
```

Las advertencias corresponden principalmente a la deprecación de `asyncio.iscoroutinefunction` en FastAPI; una advierte sobre metadata `validation_alias` de Pydantic en autenticación. Las pruebas cubren el rollback, la conexión ajena y respuestas incompletas o malformadas mediante fixtures sintéticos. No se ejecutó la suite backend completa ni PostgreSQL real; no se hicieron llamadas reales a SerpApi.

## Pendientes y límites

- Validar PostgreSQL real y el procedimiento de respaldo, restauración y migración T2 en un entorno autorizado antes de despliegue.
- Integrar y probar con HU-22 y HU-23: bandeja, dashboard, filtros y presentación de valores nulos. Los conflictos conocidos de HU-22 se resuelven en integración posterior.
- Mantener la decisión posterior del PO de conservar la importación atómica CSV/XLSX, sin importación parcial; esta tarea no modifica esa política. Cualquier cambio futuro requiere una nueva decisión.
- La ejecución sintética y la preservación de huellas no constituyen aceptación del PO ni cierre de HU-24.
