# Validación funcional integrada de Sprint 4

- Candidato: `150ddb077efa86cc904ade1ef84ac1a67b0fe94e`.
- Rama: `feature/HU-24-registro-importacion-exportacion`.
- Entorno: navegador integrado, React/Vite y FastAPI en localhost; SQLite nueva temporal, dos negocios y usuarios sintéticos. Proveedores externos deshabilitados. Se utilizaron dependencias existentes; no se instaló ninguna.
- La SQLite y la copia temporal del frontend se eliminaron al finalizar. No se conservan capturas. Los CSV descargados con datos sintéticos quedaron en Descargas como `reviews_20261117.csv` y `reviews_20261117 (1).csv`.

## Matriz de observaciones

| ID | Escenario y resultado esperado | Resultado observado | Estado |
| --- | --- | --- | --- |
| F01 | Registrar solo comentario; nueva y Manual, opcionales ausentes | Confirmación y bandeja con Sin autor, Sin fecha, Sin puntuación, Manual y Nueva. | PASS |
| F02 | Editar autor, fecha y puntuación y recargar | Autor QA, 12 mayo 2025 y 4/5 se conservaron tras recarga. | PASS |
| F03 | Cambiar y persistir estado | Nueva pasó a En revisión y se conservó al volver al dashboard. | PASS |
| F04 | Dashboard: métricas y nulos | Con dos reseñas, una 4/5 y otra sin puntuación, total 2, nueva 1, en revisión 1 y promedio 4,0. Urgentes mostró 0; no se preparó una urgente real. | PASS, alcance indicado |
| F05 | Navegar desde dashboard con filtro | En revisión abrió la bandeja con `estado=en_revision` y la reseña correspondiente. | PASS |
| F06 | Importar CSV y XLSX con celdas vacías | Cada archivo informó 1 de 1; la bandeja mostró ambas filas con fecha y puntuación ausentes. | PASS |
| F07 | Rechazar lote inválido atómicamente | CSV de dos filas, una puntuación 9: interfaz mostró error; lectura SQLite confirmó que tampoco se insertó la fila válida. | PASS |
| F08 | Filtros combinados y exportación | Búsqueda `QA CSV` y estado Nueva mostraron una fila; CSV incluyó solo id 4, campos ausentes vacíos y caracteres especiales. Otro CSV de B tuvo BOM y CRLF. | PASS, una combinación |
| F09 | Aislamiento en bandeja y dashboard | B no vio A; al regresar A no vio B. El CSV de B solo contenía B. HTTP de B: id propio 2 = 200, id ajeno 1 = 404. | PASS, alcance indicado |
| F10 | Acceso y navegación | Inicio y cierre de sesión y cabecera funcionaron con los dos usuarios de negocio. | PASS, roles administrativos pendientes |
| F11 | Exportación y acceso cruzado en ambos sentidos | No se verificó HTTP de A a B ni el CSV de A después de crear B. | BLOCKED / no ejecutado |
| F12 | Roles administrativos HU-25 | El preparador dispone de usuarios de negocio; no se verificaron roles administrativos en navegador. | BLOCKED / no ejecutado |
| F13 | Distribución y urgencia positiva | No se comprobó distribución por puntuación ni un caso urgente positivo en navegador. | BLOCKED / no ejecutado |
| F14 | Revisión integral de regresiones | La suite backend local registró seis fallos por dependencias ausentes; falta una ejecución completa en entorno con ellas. | BLOCKED |

Conteo de esta matriz: 10 PASS con el alcance descrito, 0 FAIL funcionales observados y 4 BLOCKED/no ejecutados. Las seis pruebas automatizadas fallidas se reportan abajo y no son omisiones.

## Regresión

Suite backend completa: `python -m pytest -q -p no:cacheprovider --basetemp <temporal> tests`, Python 3.14 de entorno existente, SQLite aislada, sin claves de proveedor y sin servidor PostgreSQL de prueba. Resultado: **2237 aprobadas, 6 fallidas, 37 omitidas, 5278 advertencias**. La repetición focalizada de las seis dio seis fallos: tres de `test_database_connection.py` por ausencia del módulo `psycopg`; tres de `test_priority_verification.py` por ausencia de `tzdata` y de la zona `America/Tijuana`. No se instalaron dependencias. No se atribuyen esos fallos a una regresión de HU-22/23/24 sin evidencia adicional.

GitHub Actions para el SHA indicado: `import-check`, `postgres-integration` y `build` completados con éxito. La validación PostgreSQL corresponde a CI, no a esta ejecución local.

## Complemento posterior a la matriz inicial

La matriz anterior conserva el estado histórico. Para el mismo SHA se preparó otra SQLite temporal con dos negocios, cuatro cuentas sintéticas (dos usuarios, un administrador de negocio y un administrador general) y seis reseñas por negocio. La semilla de prueba asignó puntuaciones 1–5 y NULL, prioridades y estados; no se llamó a proveedores externos. Se utilizaron React/Vite y FastAPI locales y se repitieron las comprobaciones HTTP tras recuperar la sesión. Los servidores se detuvieron después de la revisión. No se guardaron capturas.

| ID | Resultado complementario | Estado vigente |
| --- | --- | --- |
| F11 | HTTP: A consultó id propio 1 y B id propio 7 con 200; cada uno recibió 404 tanto al consultar como al editar el id ajeno. En cada negocio, búsqueda `QA TENANT` + estado `nueva` + `urgente=true` devolvió en listado y CSV el mismo id: 1 para A y 7 para B. Todos los elementos listados pertenecían al negocio autenticado; cada dashboard contó seis reseñas propias. Esto verifica la paridad por HTTP, no la descarga CSV desde navegador en esta segunda ejecución. | PASS para los casos comprobados |
| F12 | Navegador: administrador general vio el panel de negocios y guardó el nombre sintético `T6 A QA`; administrador de negocio vio Usuarios y la lista de su organización; usuario de negocio vio Resumen, Reseñas e Importaciones sin enlace Usuarios. HTTP: general obtuvo 200 en `/tenants` y 403 en `/users`, `/reviews` y `/dashboard`; admin de negocio obtuvo 200 en `/users`, `/reviews` y `/dashboard` y 403 en `/tenants`; usuario obtuvo 403 en `/users` y `/tenants` y 200 en `/reviews` y `/dashboard`. No se probaron todas las operaciones administrativas ni modificaciones de usuarios. | PASS para los controles comprobados |
| F13 | Por negocio, seis reseñas: 1–5 y NULL; promedio 3,0 y distribución HTTP de un elemento por cada puntuación. Dos urgentes: Alta/Nueva y Alta/En revisión; Alta/Atendida quedó excluida. En navegador el indicador mostró 2 y abrió la bandeja con `urgente=true` y dos filas. La paridad de CSV se comprobó por HTTP con urgencia, búsqueda y estado combinados. No se observó una gráfica de distribución en navegador. | PASS para los casos comprobados |
| F14 | Se inspeccionaron tres entornos Python existentes de HU06, Sprint2 y Sprint3: ninguno disponía de `psycopg` ni `tzdata`. No se repitieron las seis pruebas localmente. El bloqueo de cobertura backend se resuelve con los resultados de CI descritos más adelante. | BLOCKED en esta etapa histórica; resuelto por CI |

Estado consolidado antes de incorporar los resultados detallados de CI: **13 PASS para el alcance efectivamente indicado, 0 FAIL funcionales observados y 1 BLOCKED**, correspondiente a F14, el bloqueo backend por dependencias locales y PostgreSQL no configurado. No se identificó un segundo escenario funcional BLOCKED independiente en esa matriz. Los resultados anteriores de la suite local se mantienen sin cambios; las comprobaciones complementarias HTTP no sustituyen pruebas de navegador para las acciones que no se ejecutaron allí. El error de la herramienta de navegador durante la interrupción no se atribuye al producto.

## Intento de entorno backend aislado

Para el mismo SHA se creó un entorno virtual temporal fuera del repositorio con Python 3.14 de 32 bits. El proyecto declara Python >=3.13; `backend/requirements.txt` declara `psycopg[binary]>=3.2,<4.0` y `tzdata>=2024.1` en Windows. Se intentó `python -m venv <temporal>` seguido de `<temporal>/Scripts/python.exe -m pip install -r backend/requirements.txt`. La instalación terminó con `ResolutionImpossible`: el resolver no encontró una distribución compatible de `psycopg-binary` para el entorno disponible. No se modificaron entornos existentes ni archivos de dependencias. El entorno temporal no quedó preparado y no se ejecutaron de nuevo las seis pruebas ni la suite completa. Los seis fallos anteriores permanecen como tales.

La inspección de `tests/postgres/conftest.py` encontró una única omisión explícita: falta de `TEST_POSTGRES_URL`. Una recolección sin ejecución con `pytest --collect-only -q -p no:cacheprovider tests/postgres` identificó exactamente 37 casos. Esto coincide con las 37 omisiones anteriores y respalda que corresponden a PostgreSQL no configurado; el resumen detallado de omisiones de la ejecución anterior no se conservó, por lo que no se afirma una identificación individual retrospectiva. Los tests de proveedor que se inspeccionaron emplean datos sintéticos; no se identificó otro marcador de omisión explícito por servicios externos en `tests`. Los checks aprobados de PostgreSQL en GitHub Actions corresponden a CI, no a una nueva ejecución local.

## Resultados definitivos de CI aportados para el candidato

Los siguientes resultados detallados fueron proporcionados como evidencia confirmada de los trabajos aprobados asociados al SHA `150ddb077efa86cc904ade1ef84ac1a67b0fe94e`. En el intento anterior de auditoría no se pudo acceder directamente a sus logs; los valores siguientes se registran según la evidencia aportada, sin atribuirlos a una ejecución local.

| Trabajo | Comando del workflow | Entorno y resultado |
| --- | --- | --- |
| [Backend general: import-check](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/actions/runs/44166866206/job/134335143529) | `python -m pytest --ignore=tests/postgres` | Linux, Python 3.13.18 x64, pytest 8.4.2; 2243 recolectadas, **2243 aprobadas, 0 fallidas, 0 omitidas**, 1 advertencia, 264,93 s. |
| [PostgreSQL: postgres-integration](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/actions/runs/44166866206/job/134335144094) | `python -m pytest tests/postgres -q` | PostgreSQL 17; **37 aprobadas, 0 fallidas, 0 omitidas**, 1 advertencia, 9,85 s. |

En total, CI reporta **2280 aprobadas, 0 fallidas y 0 omitidas**. El comando general incluye los seis casos que fallaron localmente y finalizó sin fallos ni omisiones; el trabajo PostgreSQL ejecutó satisfactoriamente 37 casos. Esta evidencia cubre el bloqueo de F14 en CI. La ejecución local conserva su resultado histórico de 2237 aprobadas, 6 fallidas y 37 omitidas; no se reejecutó ni se transforma en una aprobación local.

## Dictamen vigente

**Bloqueo técnico backend resuelto mediante CI**, sujeto a la evidencia detallada aportada. F14 era el único BLOCKED identificado en la matriz funcional histórica; no se debe interpretar su resolución como aprobación automática de escenarios no ejecutados. Siguen pendientes la descarga y paridad CSV en navegador para ambos negocios en la segunda ejecución, la gráfica de distribución en navegador si forma parte del alcance aceptado, la cobertura de las operaciones administrativas no ejercitadas y la aceptación funcional del equipo/PO. La importación parcial sigue sujeta a decisión del PO; SerpApi real no fue validado en estos recorridos. No se declara HU-24 terminada ni se modifica el PR o OpenProject.
