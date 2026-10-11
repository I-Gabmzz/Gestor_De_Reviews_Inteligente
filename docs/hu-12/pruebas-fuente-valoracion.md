# HU-12 — T3 #3559: pruebas de fuente, valoración y visualización

Fecha: 10 de octubre de 2026. Rama: `feature/HU-12-fuente-valoracion`. HEAD inicial: `ec8e45ca9e450a60812fc8e4c6b8c0c1a7c84d80` (T2). La rama estaba limpia y sincronizada con `origin/feature/HU-12-fuente-valoracion`; el commit de T1 `55a58679e027b4a125bd39b55602da5c2a836cae` estaba en el historial.

## Objetivo y entorno

Validar la asignación, edición, persistencia, visualización y filtrado de `fuente` y `puntuacion`, además del aislamiento entre tenants, sin cambiar código funcional. Se usaron Python 3.13.5 en `backend/.venv`, SQLite, Node.js 20.20.2 y npm 10.8.2. La prueba de interfaz usó una base separada `backend/.venv/hu12_t3_ui.db`, creada con `scripts.seed_demo`, y servidores locales FastAPI (`localhost:8000`) y Vite (`localhost:5173`). Los datos de prueba quedaron fuera de Git.

## Casos y resultados

| Escenario | Resultado esperado | Resultado obtenido y evidencia |
| --- | --- | --- |
| Registro manual con puntuación 5 | La fuente se asigna como `manual`; listado y detalle muestran `manual/5`. | **Aprobado en interfaz.** Se creó `T3 registro manual visual`; el listado mostró `manual` y `5`, y el detalle mostró la misma fuente y puntuación. Tras recargar, seguía presente. También lo cubre `test_registrar_review_manual_persiste_con_valores_de_servidor` en `backend/tests/test_reviews_api.py`. |
| CSV sin fuente o con fuente vacía | Se asigna `CSV`. | **Aprobado por API automatizada** en los casos parametrizados de `test_importacion_asigna_fuente_por_formato_si_falta_o_esta_vacia` (`backend/tests/test_imports_api.py`). |
| XLSX sin fuente o con fuente vacía | Se asigna `Excel`. | **Aprobado por API automatizada** en el mismo test parametrizado. |
| CSV/XLSX con fuente proporcionada | Se conserva la fuente normalizada y la puntuación. | **Aprobado por API automatizada** en `test_ambos_endpoints_conservan_fuente_proporcionada_y_puntuacion`. **Aprobado en interfaz para CSV**: se importó `T3 CSV visual` con `Google/4`; la pantalla informó `1 de 1 filas válidas` y listado/detalle mostraron `Google/4`. XLSX no se cargó desde la interfaz. |
| Fuente de 100 y 101 caracteres | Se aceptan 100 caracteres tras recortar espacios; 101 invalidan el lote completo. | **Aprobado por API automatizada** para CSV y XLSX en `test_importacion_acepta_fuente_de_cien_caracteres_tras_normalizar` y `test_fuente_demasiado_larga_invalida_todo_el_lote`. El lote de dos filas guardó cero cuando una fuente tenía 101 caracteres. |
| Edición y persistencia | Cambiar fuente y puntuación; conservar los campos omitidos. | **Aprobado en interfaz y API.** La review importada cambió de `Google/4` a `Booking/5`; listado y detalle se actualizaron, y la review seguía con `Booking/5` después de recargar. `test_editar_campos_permitidos_persiste_sin_modificar_campos_protegidos` y `test_edicion_parcial_conserva_campos_omitidos` verifican persistencia y actualización parcial. |
| Valores inválidos de edición | Rechazar puntuaciones fuera de 1–5 y fuentes vacías, nulas o de más de 100 caracteres sin alterar la review. | **Aprobado por API automatizada** en los casos parametrizados de `test_datos_invalidos_no_guardan_cambios` (`backend/tests/test_review_edit_api.py`). No se repitió cada error en la interfaz. |
| Filtros por fuente, puntuación y ambos | Devolver solamente coincidencias del tenant; la fuente debe compararse exactamente y distinguir mayúsculas. | **Aprobado en interfaz y API.** `Booking` + `5` mostró una review; `booking` + `5` mostró cero. `test_listado_http_busqueda_filtros_total_orden_y_tenant` cubre filtros individuales, combinados y `Google` frente a `google`/`GOOGLE`. |
| Aislamiento entre tenants | Listado, detalle, edición e importación no exponen ni modifican otro tenant. | **Aprobado por API automatizada.** `test_listar_reviews_devuelve_solo_el_tenant_autenticado`, `test_review_ajena_o_inexistente_devuelve_404`, `test_editar_review_ajena_o_inexistente_no_revela_datos`, `test_combinacion_http_aisla_ambos_tenants` y `test_importacion_ignora_tenant_id_manipulable_en_query` comprueban la separación. No se hizo sesión visual con un segundo tenant. |

## Recorrido visual y evidencia

Se ejecutó en el navegador la secuencia **Login → Dashboard → Importación CSV → Listado → Detalle → Edición → Filtros**, seguida de registro manual y recarga. La cuenta local de demostración mostró inicialmente 3 reviews y promedio 4.0. Tras la importación, el listado mostró 4 reviews; tras el registro manual, 5. El detalle y la tabla mostraron los mismos valores de fuente y puntuación para las dos reviews de T3. La recarga confirmó persistencia. Las observaciones se hicieron sobre respuestas de la interfaz, no mediante inspección de código.

El recorrido visual no incluyó carga XLSX, los casos de fuente ausente/vacía ni las validaciones de 100/101 caracteres. Esos casos sí se ejecutaron mediante `backend/tests/test_imports_api.py` dentro de la suite completa. Tampoco se probó visualmente una segunda cuenta de tenant; la evidencia alternativa está en las pruebas API indicadas arriba.

## Verificaciones automatizadas y regresiones

| Verificación | Resultado |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -q -ra --tb=short --basetemp backend/.venv/pytest-hu12-t3-final` | **366 aprobadas, 0 fallidas, 1 advertencia** en 116.98 s. Misma cantidad de aprobadas que en T2. La advertencia es `StarletteDeprecationWarning` sobre `httpx` en `starlette.testclient`. |
| `npm run lint` en `frontend` | **Aprobado**; ESLint terminó con código 0. |
| `npm run build` en `frontend` | **Aprobado**; Vite 7.3.6 transformó 1751 módulos y terminó en 5.89 s. |
| `git diff --check` | **Aprobado**; sin errores de espacios. |

Un primer intento de suite coincidió con otro proceso pytest que quedó activo y bloqueó el mismo `test.db` temporal en Windows; produjo errores de preparación por `WinError 32`. Se detuvo aquel proceso y se repitió la suite en una ruta temporal nueva: las 366 pruebas pasaron. El primer intento de build recibió `EPERM` del entorno de ejecución; al repetirlo con acceso normal de lectura pasó. Ninguno de esos errores se reprodujo en la ejecución final.

## Conclusión técnica

No se detectó un defecto funcional de HU-12 ni una regresión respecto a T2. La asignación de fuente por origen, los límites de validación, la edición, la visualización, los filtros exactos y el aislamiento por tenant tienen cobertura automatizada satisfactoria; el flujo principal también se comprobó en la interfaz con CSV y registro manual. **HU-12 está lista para revisión mediante Pull Request**, con las limitaciones visuales señaladas. T3 no cambió código funcional ni dependencias.
