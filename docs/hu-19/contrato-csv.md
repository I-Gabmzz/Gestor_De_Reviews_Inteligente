# HU-19 / T1 #3821 — Contrato de exportación CSV filtrada

## Propósito y alcance

HU-19 #3233 permite que un usuario de negocio exporte las reviews de su tenant para utilizarlas fuera de la plataforma. La historia exige los datos principales, los campos disponibles de contenido, autor, fecha, fuente, puntuación, categoría y estado, los filtros aplicados, aislamiento entre tenants y un archivo comprensible que pueda abrirse. La alternativa inicial aprobada para este alcance es **CSV**; la historia permite CSV o Excel, pero este contrato no define un archivo `.xlsx`.

T1 #3821 define columnas, orden, UTF-8, nulos y alcance de filas. Su evidencia de cierre es este contrato junto con [`ejemplo-reviews.csv`](./ejemplo-reviews.csv). La estimación oficial de T1 es 2 horas. Las referencias de requisitos son los PDF de OpenProject de HU-19 #3233 y T1 #3821 facilitados por el responsable. El responsable comunicó que el Product Owner, David Escárcega, autorizó el contrato; el ejemplo se preparó después para su revisión. Aquí no se afirma que exista un registro formal de aprobación en OpenProject ni se registra una fecha o firma de aprobación.

Este documento fija el contrato para el trabajo posterior. No describe un endpoint ni una descarga ya implementados.

## Columnas y representación

Los encabezados son técnicos, estables y sensibles a su escritura exacta. Se emiten siempre en este orden:

| Orden | Encabezado | Tipo exportado | Representación |
| ---: | --- | --- | --- |
| 1 | `id` | Entero | Identificador de la review para comparar lista y exportación. |
| 2 | `contenido` | Texto | Contenido completo, incluidos comillas y saltos de línea. |
| 3 | `autor` | Texto o vacío | Valor almacenado; si es nulo, celda vacía. No usar «Anónimo». |
| 4 | `fecha` | Texto ISO 8601 | Fecha y hora almacenadas, sin añadir una zona horaria inexistente. |
| 5 | `fuente` | Texto | Valor almacenado. |
| 6 | `puntuacion` | Entero | Valor numérico, sin estrellas ni etiquetas. |
| 7 | `categoria` | Texto o vacío | Valor almacenado; si es nulo, celda vacía. |
| 8 | `estado` | Texto | Valor técnico almacenado, como `nueva`, `en_revision` o `atendida`. |

No se incluyen inicialmente `tenant_id`, `prioridad`, `resumen` ni `tema`. El primero es una condición de aislamiento, no una columna de exportación; los demás quedan fuera del conjunto aprobado de campos principales. Las celdas nulas son vacías, sin `null`, `N/A` ni sustituciones visuales. El modelo y el schema actuales se encuentran en `backend/app/models/review.py` y `backend/app/schemas/review.py`.

## Filtrado, alcance y orden

Se exportan **todas** las reviews del tenant autenticado que coincidan con los filtros activos, no solo la review seleccionada en la interfaz. Los criterios son exactamente los seis de HU-10: `busqueda` (coincidencia parcial en contenido), `fecha_desde`, `fecha_hasta` (día final inclusive), `puntuacion`, `estado` y `fuente` (igualdad exacta). Se mantienen la normalización y validación actuales de `ReviewService.list_by_tenant` y `ReviewRepository.list_by_tenant`; la exportación no debe crear una segunda interpretación de los filtros.

El orden es `fecha DESC, id DESC`, como en el listado actual. La consulta existente todavía no tiene paginación. Si se incorpora posteriormente, este contrato sigue refiriéndose a todas las coincidencias de los filtros, no solo a la página visible. Una solicitud sin filtros comprende todas las reviews del tenant autorizado.

El `tenant_id` procede exclusivamente del usuario autenticado y validado en el backend. Un `tenant_id` enviado o alterado por el cliente no puede seleccionar un negocio ajeno.

## Formato del archivo

| Propiedad | Contrato |
| --- | --- |
| Tipo | CSV (`.csv`). |
| Codificación | UTF-8 **con BOM**: bytes iniciales `EF BB BF`. El BOM favorece la detección de UTF-8 en hojas de cálculo; un lector programático puede usar `utf-8-sig`. |
| Separador | Coma `,`. |
| Comillas | Comillas dobles conforme a las reglas CSV; una comilla interna se duplica. Se entrecomillan los campos que lo requieran por coma, comillas o salto de línea. |
| Fin de registro | `CRLF` (`\r\n`). Un salto de línea dentro de `contenido` permanece dentro de la celda entrecomillada. |
| Encabezados | Siempre presentes, con los ocho nombres y el orden de la tabla anterior. |
| Sin coincidencias | CSV con BOM y encabezados, sin filas de datos. |
| Nombre propuesto | `reviews_YYYYMMDD.csv`, con la fecha de generación. |
| Respuesta HTTP futura | `Content-Type: text/csv; charset=utf-8` y `Content-Disposition: attachment`. |

El BOM no cambia el significado de UTF-8. Su lectura y la interpretación de la coma en la hoja de cálculo elegida se comprobarán en T5.

## Autorización y seguridad multi-tenant

La exportación corresponderá a usuarios autenticados con rol `usuario_negocio` o `admin_tenant`, vinculados a un tenant activo. `admin_general` no obtiene acceso global a las reviews mediante esta función. Los controles deben aplicarse en FastAPI incluso ante una solicitud directa a la API; ocultar la acción en React no sustituye la autorización. Deben reutilizarse el contexto de usuario y tenant vigente y el filtro SQL `Review.tenant_id == tenant_id`.

La exportación es de solo lectura: no altera reviews ni otros datos persistidos. El archivo no contiene datos de otros tenants aunque el cliente manipule filtros o parámetros.

## Texto con apariencia de fórmula

Una celda de texto cuyo contenido efectivo comience con `=`, `+`, `-` o `@` puede ser interpretada por algunas hojas de cálculo como fórmula. Para la exportación se antepone un apóstrofo a la celda de texto cuando, tras espacios o caracteres de control iniciales, aparezca uno de esos prefijos. La comprobación aplica a todas las columnas de texto exportadas. Se conservan los caracteres originales después del apóstrofo y **no se modifica el valor persistido**. Las columnas numéricas se serializan como números del modelo, no como texto de entrada.

Esta neutralización introduce una diferencia entre la celda exportada y el valor original. No se presenta como garantía universal: T5 debe probarla con las hojas de cálculo previstas, además de comprobar Unicode, comillas, comas, saltos de línea y volumen acordado. Si una aplicación interpreta el contenido de forma insegura o modifica su visualización, se revisará el mecanismo con el PO antes de declarar completada la validación.

## Ejemplo sintético

El archivo [`ejemplo-reviews.csv`](./ejemplo-reviews.csv) contiene exclusivamente datos ficticios y demuestra las ocho columnas, acentos y ñ, comillas, coma, salto de línea dentro de `contenido`, nulos, texto con apariencia de fórmula neutralizado y orden descendente por fecha. La representación visual de un CSV no muestra el BOM; las comprobaciones de bytes deben verificarlo.

## Trazabilidad de criterios oficiales

| Criterio de HU-19 o T1 | Decisión del contrato | Evidencia o prueba prevista |
| --- | --- | --- |
| Reviews del tenant y ninguna de otro | Tenant del usuario autenticado y condición SQL obligatoria | T2/T4: usuarios de dos tenants y parámetros manipulados. |
| Datos principales y siete campos nombrados | `contenido`, `autor`, `fecha`, `fuente`, `puntuacion`, `categoria`, `estado`, más `id` para trazabilidad | T2/T4: encabezados y valores. |
| Respetar filtros aplicados | Reutilizar los seis criterios de HU-10 | T2/T3/T4: parámetros, conjunto y orden de resultados. |
| CSV o Excel inicialmente | CSV como formato inicial | T3/T5: descarga y apertura del archivo. |
| Archivo legible y estructurado | Encabezados fijos, coma, comillas CSV, CRLF, UTF-8 con BOM | T5: lector CSV y hoja de cálculo. |
| T1: columnas y orden | Ocho columnas fijas; filas por `fecha DESC, id DESC` | Ejemplo y T4. |
| T1: UTF-8 | UTF-8 con BOM | Ejemplo y T5. |
| T1: nulos | Celdas vacías | Ejemplo y T5. |
| T1: alcance de filas | Todas las coincidencias del tenant, independientes de selección | T2/T4. |
| T1: ejemplo y contrato aprobados | Contrato autorizado según el responsable; ejemplo sintético preparado para revisión | Aprobación del ejemplo y cierre administrativo pendientes de su proceso. |

## Validaciones posteriores y asuntos abiertos

- **T2:** probar filtros, orden, permisos, aislamiento entre tenants, respuesta CSV y cero resultados.
- **T3:** probar envío de filtros actuales, descarga y error sin alterar filtros ni selección de la interfaz.
- **T4:** comparar lista y archivo con dos tenants, cero filas y todos los campos exigidos; conservar evidencia sintética, CI y demostración.
- **T5:** probar Unicode, comillas, comas, saltos de línea, fórmulas y el volumen acordado; abrir el CSV sin datos privados.

Quedan por concretar el **límite de volumen** y la hoja de cálculo de referencia para la validación de T5. El nombre `reviews_YYYYMMDD.csv` está propuesto para la implementación y debe ratificarse si se requiere una convención distinta. Estos asuntos no modifican las columnas, filtros, aislamiento ni formato aquí autorizados.
