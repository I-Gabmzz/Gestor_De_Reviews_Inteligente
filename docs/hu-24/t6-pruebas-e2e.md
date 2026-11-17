# HU-24 / T6 — Integración y preparación E2E

Estado: recorridos en navegador real y pruebas de integración ejecutados; **T6 no está completada**. T6-11 y T6-12 fueron completadas en ejecuciones posteriores. Permanecen pendientes HU-22/HU-23 y PostgreSQL real. Base de la primera ejecución: `0adfb8214132c338dd0ed68fcc3f200c6139569e`.

## Entorno y alcance

Las pruebas HTTP usan FastAPI TestClient, una base SQLite temporal por prueba y usuarios sintéticos. Las pruebas frontend usan Node, React, JSDOM y respuestas HTTP simuladas. Ninguna de estas pruebas es un E2E de navegador real. Las pruebas de proveedor externo usan el transporte simulado de HU-21; no se contactó SerpApi.

La nueva prueba `backend/tests/test_hu24_t6_http_journey.py` recorre en una sola base temporal autenticación de dos tenants, alta mínima y completa, validaciones, edición, CSV/XLSX, rechazo atómico, listado, exportación y persistencia NULL. Se amplían las pruebas JSDOM de alta completa y edición que conserva nulos. `backend/scripts/hu24_t6_local.py` prepara una base nueva y dos usuarios sintéticos para la futura validación manual.

## Matriz histórica inicial de integración

Esta tabla refleja únicamente el estado inicial de integración y no el estado vigente. La matriz consolidada posterior recoge los resultados de navegador y las ejecuciones complementarias.

| ID | Escenario y resultado esperado | Tipo y resultado obtenido | Estado | Dependencia / evidencia |
|---|---|---|---|---|
| T6-01 | Alta con opcionales vacíos: NULL sin datos inventados | HTTP y JSDOM: NULL confirmados | Aprobada en integración; navegador no ejecutado | `test_hu24_t6_http_journey.py`, `hu24OptionalReviews.integration.test.mjs` |
| T6-02 | Alta completa: valores conservados | HTTP y JSDOM: alta y payload confirmados | Aprobada en integración; navegador no ejecutado | Mismos archivos |
| T6-03 | Contenido vacío: rechazo sin escritura | HTTP 422 y mensaje JSDOM | Aprobada en integración; navegador no ejecutado | Mismos archivos |
| T6-04 | Puntuación inválida: rechazo | HTTP 422; JSDOM comprueba 0/6 en edición | Aprobada en integración; navegador no ejecutado | T3, mismos archivos |
| T6-05 | Editar manteniendo nulos | HTTP y JSDOM conservan nulos | Aprobada en integración; navegador no ejecutado | T3, mismos archivos |
| T6-06 | Importar CSV con celdas vacías | HTTP guarda una fila con tenant de sesión; JSDOM comprueba multipart | Aprobada en integración; navegador no ejecutado | T4, tests HTTP T6 y `externalReviewImport.integration.test.mjs` |
| T6-07 | Importar XLSX con celdas vacías | HTTP guarda una fila; JSDOM comprueba multipart | Aprobada en integración; navegador no ejecutado | T4, mismos tests |
| T6-08 | Archivo con fila inválida: rechazo atómico | HTTP informa cero guardadas y listado no incluye fila válida del lote | Aprobada en integración; navegador no ejecutado | T4, test HTTP T6 |
| T6-09 | Consultar reseñas importadas | Listado HTTP confirma cuatro reseñas del tenant | Aprobada en integración; navegador no ejecutado | Test HTTP T6 |
| T6-10 | Exportar CSV con celdas vacías y orden del listado | HTTP verifica BOM, ocho columnas, nulos e IDs; JSDOM verifica descarga simulada | Aprobada en integración; navegador no ejecutado | T4, test HTTP T6 y `reviewExport.integration.test.mjs` |
| T6-11 | Dos tenants aislados | HTTP rechaza lectura y edición ajenas y verifica listado/exportación de ambos | Aprobada en integración; navegador no ejecutado | Test HTTP T6 |
| T6-12 | Reseña Google externa con nulos y tenant correcto | HTTP con proveedor simulado prueba inserción y reimportación para ambos tenants | Aprobada en integración; navegador no ejecutado | `test_external_review_import_api.py` |
| T6-13 | Dashboard y filtros con nulos | No ejecutado: esquema actual de dashboard exige fecha y puntuación | Bloqueada | HU-23 y validación posterior a integración |

## Comandos y resultados

Backend, desde `backend/`, con Python del entorno virtual existente de Sprint 3, `DATABASE_URL=sqlite://`, credenciales de proveedor retiradas y `--basetemp` en un directorio temporal:

```text
python -m pytest tests/test_hu24_t6_http_journey.py tests/test_hu24_t3_http.py tests/test_hu24_t4_import_export.py tests/test_external_review_import_api.py -q -p no:cacheprovider
162 passed, 1955 warnings in 29.07s
```

Después se añadió la comprobación de exportación del segundo tenant y se repitió la prueba nueva: `python -m pytest tests/test_hu24_t6_http_journey.py -q -p no:cacheprovider`, con **1 passed, 95 warnings in 1.44s**. La regresión de 162 casos corresponde a la versión anterior a esa última aserción.

Frontend en una copia temporal con las dependencias ya existentes de Sprint 3, sin instalar paquetes:

```text
node --test --test-concurrency=1 tests/hu24OptionalReviews.integration.test.mjs tests/externalReviewImport.integration.test.mjs tests/reviewExport.integration.test.mjs
66 passed, 0 failed, 0 skipped; 13.95 s
npm run lint: aprobado
npm run build: aprobado; 1773 módulos
```

Pytest mostró advertencias de deprecación de FastAPI y una advertencia de metadata de Pydantic; Node mostró avisos de futuras opciones de React Router. No se ejecutó PostgreSQL real ni la suite backend completa. Una primera invocación de comprobación del preparador falló por comillas en el comando; la repetición con entrada estructurada pasó.

## Preparación para navegador real

Con las dependencias existentes instaladas o disponibles, ejecutar desde `backend/`:

```text
python -m scripts.hu24_t6_local
```

El script crea un directorio temporal nuevo, comprueba la ruta SQLite antes de inicializar, fija la URL antes de importar la aplicación, deshabilita la migración de bases antiguas y la importación externa, crea dos usuarios sintéticos y muestra datos de acceso temporales solo en consola. No conservar ni publicar esa salida. Al finalizar con Ctrl+C cierra el motor y elimina el directorio temporal. Antes de la sesión de navegador se comprobó creación de la base, dos usuarios y limpieza con el arranque de Uvicorn simulado; la sesión real posterior se detalla más abajo.

En otra terminal, desde una copia segura de `frontend/`, establecer `VITE_API_URL=http://127.0.0.1:8000/api/v1` e iniciar `npm run dev -- --host localhost`. Abrir el origen de Vite permitido por CORS, iniciar sesión con los usuarios temporales y recorrer T6-01 a T6-11. Generar CSV/XLSX con datos sintéticos y los encabezados `contenido,fecha,puntuacion`; comparar las descargas con el listado. No abrir el dashboard como criterio aprobado mientras HU-23 esté pendiente. El preparador deshabilita la importación externa: T6-12 en navegador requiere un harness adicional que inyecte el proveedor simulado de HU-21, sin servicios externos.

## Dependencias y limitaciones

- HU-22: resolver los conflictos conocidos antes de validar la bandeja integrada.
- HU-23: dashboard y filtros con NULL, orden de nulos y fecha máxima pendientes.
- PostgreSQL real: no ejecutado; migración T2 y respaldo/restauración requieren entorno autorizado.
- No se instaló Playwright ni Cypress y no existe runner de navegador configurado. Se requieren ejecución manual real o acuerdo para automatizarla.
- No se cambia la política atómica ni se cierra administrativamente HU-24.

## Matriz consolidada vigente tras las ejecuciones E2E de T6-11 y T6-12

El 16 de noviembre de 2026 se utilizó el navegador integrado de la aplicación con Vite en `localhost:5173` y FastAPI en `127.0.0.1:8000`. El preparador creó una SQLite nueva en su propio directorio temporal y dos usuarios sintéticos; `VITE_API_URL` apuntó expresamente al backend local. Los archivos CSV/XLSX se generaron con datos sintéticos. La evidencia de interfaz consiste en los estados de accesibilidad observados durante la sesión; no se guardaron capturas. Se consultaron en modo lectura el CSV descargado y la SQLite temporal antes de terminar el entorno.

| ID | Pasos y resultado esperado | Resultado y evidencia | Estado |
|---|---|---|---|
| T6-01 | Registrar solo contenido | Confirmación de guardado; listado y detalle muestran anónimo, sin fecha y sin puntuación; SQLite confirma NULL | Aprobada |
| T6-02 | Registrar autor, fecha, contenido y 5 | Confirmación y fila con autor, fecha y 5/5; base confirma datos | Aprobada |
| T6-03 | Enviar formulario sin contenido | Se mostró «Escribe el contenido de la review»; no se añadió fila | Aprobada |
| T6-04 | Introducir 6 en edición | Mensaje de puntuación fuera de rango; regresión HTTP complementa valores inválidos | Aprobada para el control comprobado |
| T6-05 | Editar contenido de la reseña sin opcionales | Confirmación y detalle sin fecha/puntuación; SQLite conserva autor, fecha y puntuación NULL | Aprobada |
| T6-06 | Subir CSV con celdas vacías | Interfaz confirma 1 de 1 guardada; listado y base muestran nulos | Aprobada |
| T6-07 | Subir XLSX con celdas vacías | Interfaz confirma 1 de 1 guardada; listado y base muestran nulos | Aprobada |
| T6-08 | Subir CSV con fila válida y puntuación 6 | Error por puntuación; la fila válida del lote no aparece en listado ni SQLite | Aprobada para CSV |
| T6-09 | Consultar ambas importaciones | Listado muestra CSV y XLSX, sus fuentes y campos ausentes | Aprobada |
| T6-10 | Descargar CSV de A | Archivo descargado: BOM UTF-8, CRLF, ocho columnas, cuatro filas y celdas vacías correspondientes | Aprobada |
| T6-11 | Cambiar a B y consultar/crear | En la primera ejecución B no vio A y vio su propia reseña; faltó volver a entrar como A. La segunda ejecución bidireccional se documenta abajo | Aprobada en segunda ejecución |
| T6-12 | Importación externa con proveedor simulado | Pendiente en esta primera sesión; se completó en una ejecución posterior documentada abajo | Aprobada en ejecución posterior |
| T6-13 | Dashboard y filtros integrados con nulos | No ejecutado como aceptación integrada | Bloqueada por HU-23 |

La descarga contiene únicamente datos sintéticos. El proveedor real y PostgreSQL no se utilizaron. La consola del preparador mostró credenciales efímeras de prueba, que no se incluyen en este documento.

Regresión repetida después de los recorridos con los cuatro archivos pytest indicados arriba: **162 passed, 1955 warnings in 33.06s**, sin fallos ni omisiones. Los tres archivos Node indicados arriba se repitieron con `--test-reporter=dot`: **66 aprobadas**, código 0. `npm run lint` y `npm run build` pasaron en la copia temporal; el build transformó 1773 módulos. Las advertencias son las mismas familias de FastAPI y Pydantic descritas arriba. `git diff --check` se verificó al final.

## T6-11 — Segunda ejecución bidireccional en navegador

Sobre HEAD `18492505b57b2df7beb609226ae3b7fdb887191b`, se inició el navegador integrado con Vite local, FastAPI y una SQLite temporal nueva creada por el preparador, con dos usuarios sintéticos. No se usaron datos reales ni SerpApi. Las observaciones de interfaz fueron estados de accesibilidad; no se guardaron capturas ni credenciales.

- Tenant A creó la reseña sintética **ID 1**, la vio en listado y detalle y exportó un CSV que contenía exclusivamente ID 1.
- Tras cerrar sesión, tenant B no vio la reseña de A; creó **ID 2**, la vio en listado y detalle y exportó un CSV que contenía exclusivamente ID 2.
- Después de volver a iniciar sesión como A, su listado y una nueva exportación contenían solo ID 1, sin la reseña de B.
- Mediante HTTP local autenticado, A consultó su ID 1 con **200** y el ID 2 ajeno con **404**; B consultó su ID 2 con **200** y el ID 1 ajeno con **404**. Las respuestas de rechazo no contenían el texto de la otra reseña.
- Los tres CSV descargados se verificaron: ocho columnas, BOM UTF-8, CRLF y celdas vacías para autor, fecha y puntuación. Cada uno contenía únicamente la fila del tenant correspondiente.
- La lectura de SQLite antes de la limpieza confirmó dos reseñas: ID 1 en tenant 10 e ID 2 en tenant 20, ambas de fuente `manual` y con los campos opcionales NULL.

**Resultado T6-11: aprobada para este recorrido bidireccional en SQLite.** Al regresar a A, el dashboard mostró un error de carga con una reseña sin opcionales; corresponde al bloqueo de dashboard HU-23 y no se consideró resultado de T6-11. Al finalizar esta ejecución, T6-12 todavía estaba pendiente; posteriormente se ejecutó y aprobó según la sección siguiente. T6-13, integración HU-22/HU-23 y PostgreSQL real permanecen pendientes.

## T6-12 — Importación externa simulada en navegador

En una ejecución posterior sobre HEAD `18492505b57b2df7beb609226ae3b7fdb887191b` se usó el navegador integrado con React/Vite y FastAPI sobre una SQLite temporal nueva. Un helper efímero en memoria reutilizó el preparador T6 y configuró únicamente en esa base una conexión Google autorizada del tenant A. Sobrescribió las dependencias de política y servicio solo en la aplicación de prueba e inyectó `SerpApiClient` con `httpx.MockTransport`, siguiendo el patrón de las pruebas de HU-21. El transporte HTTP real de httpx se bloqueó en ese proceso. La autenticación, la comprobación de actor, conexión y procedencia, y la persistencia conservaron su implementación real. No se utilizaron credenciales reales ni se llamó a SerpApi.

El proveedor sintético devolvió un establecimiento válido `0xabc:0x123`, una reseña con identidad `t612-synthetic-id`, fuente `Google` y contenido sintético, sin autor, fecha ni puntuación. En el navegador, A seleccionó su establecimiento y la interfaz informó **1 obtenida, 1 insertada y 0 repetidas**; al repetir, informó **0 insertadas y 1 repetida**. El listado y detalle mostraron el contenido, fuente Google, «Sin fecha» y «Sin puntuación». Tras cambiar de sesión, el listado del tenant B apareció vacío. La evidencia de interfaz son los estados de accesibilidad observados; no se guardaron capturas.

La lectura de SQLite confirmó una sola reseña **ID 1, tenant 10**, fuente Google y autor/fecha/puntuación SQL NULL; la identidad externa única conserva el establecimiento y el identificador sintéticos. Se registraron dos intentos. El detalle HTTP autenticado de A respondió **200** con los tres nulos; el detalle solicitado por B respondió **404** sin revelar el contenido y el listado de B respondió **200** vacío. El resultado visible de importación fue confirmado por la interfaz; no se registraron por separado los códigos HTTP de los dos POST desde el navegador.

**Resultado T6-12: aprobada para este recorrido en navegador con proveedor simulado y SQLite temporal.** No valida SerpApi real ni PostgreSQL. Se mantienen pendientes T6-13 e integración HU-22/HU-23. Los servidores se detuvieron y la copia temporal se eliminó. El cierre dejó inicialmente el directorio de SQLite; se verificaron su ruta y contenido y se eliminó después. No se modificó ninguna base existente.
