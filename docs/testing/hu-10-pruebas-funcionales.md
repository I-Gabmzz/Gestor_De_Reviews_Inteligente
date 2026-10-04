# HU-10 - Pruebas funcionales de busqueda y filtrado

- Historia de usuario: HU-10 (#3237).
- TASK: #3335 - Probar busqueda y filtrado de reviews.
- Estado de la validacion: PASS. Las ocho TASK de HU-10 quedan completas tecnicamente, sujetas a auditoria final y PR.

## Objetivo y entorno

Validar desde `ReviewsPage` hasta `GET /api/v1/reviews` y la base de datos que la busqueda y los filtros devuelven exclusivamente las reviews coincidentes del tenant autenticado. Se uso el frontend React local, el backend FastAPI local, un navegador automatizado y SQLite temporal. La base y el proceso backend temporales se eliminaron o detuvieron al terminar. No se uso informacion real ni se guardaron credenciales o tokens en el repositorio.

Los datos ficticios incluyeron siete reviews del Tenant A, dos del Tenant B y un Tenant C sin reviews. Hubo puntuaciones de 1 a 5, los tres estados tecnicos, fuentes distintas, fechas entre el 10 y el 21 de septiembre de 2026, una review del dia 20 a las 23:59:59.999999 y contenido coincidente deliberadamente entre A y B. Se agrego una review manual temporal para la regresion de HU-06/HU-08/HU-09.

Las pruebas de la matriz funcional se realizaron antes de detectar el desbordamiento responsive y se repitio una regresion representativa despues del fix `2c86f405a99e179d2302005974d4bfea289fc044`. Todos los resultados finales indicados abajo son posteriores al fix o permanecieron cubiertos por la suite backend completa.

## Matriz funcional

| Caso | Esperado | Obtenido | Estado |
|---|---|---|---|
| Listado sin criterios | Siete reviews del Tenant A, ordenadas por fecha e id descendentes | `total=7`; tabla actualizada desde la API | PASS |
| Busqueda parcial y sin importar mayusculas | Coincidencias en `contenido`; `lento` y `SERVICIO` devuelven 3 y 5 | 3 y 5; request con `busqueda` | PASS |
| Frase completa y espacios exteriores | `servicio lento` encuentra la frase; los espacios exteriores no cambian el criterio | 2 coincidencias; trim comprobado antes del fix, busqueda repetida despues | PASS |
| `%` y `_` literales | `100%` y `servicio_lento` no actuan como comodines | Una coincidencia literal en cada caso | PASS |
| Busqueda sin resultados y limpieza | Estado sin coincidencias; al limpiar vuelve el listado sin `busqueda` | Mensaje de ausencia de coincidencias y luego `total=7` | PASS |
| Solo `fecha_desde` / solo `fecha_hasta` | Desde el 20: 2; hasta el 20: 6 | 2 y 6 | PASS |
| Rango y mismo dia | Rango 10-20: 6; solo el dia 20: 1 | 6 y 1 | PASS |
| Dia final completo | La review del 20 a las 23:59:59.999999 debe incluirse | Incluida en `fecha_hasta=2026-09-20` | PASS |
| Rango sin resultados / invertido | Cero resultados / HTTP 422 con mensaje comprensible | `total=0` / 422 y alerta legible | PASS |
| Puntuaciones 1, 2, 3, 4 y 5 | Coincidencia exacta; totales 1, 2, 1, 1 y 2 | Totales esperados; combinacion imposible da cero | PASS |
| Estados | Etiquetas Nueva, En revision y Atendida; valores API `nueva`, `en_revision`, `atendida` | Totales 3, 1 y 3; valores tecnicos en requests | PASS |
| Fuente | Igualdad exacta; `Google` 3, `CSV` 1, `google` e inexistente 0 | Totales esperados; limpieza restaura el listado | PASS |
| Combinaciones AND | Busqueda+estado, puntuacion+fuente, fecha+puntuacion, varios filtros y seis criterios | Cada agregado redujo el conjunto; los seis criterios dieron una review; combinacion imposible dio cero | PASS |
| Limpiar filtros / limpiar busqueda | Cada accion conserva el otro grupo; limpiar ambos restaura el listado | Requests con solo `busqueda`, solo `puntuacion` y sin parametros, respectivamente | PASS |
| Actualizar con criterios activos | Repetir los seis parametros sin borrarlos | Nueva request con los seis criterios y un resultado | PASS |
| Detalle excluido | No mostrar detalle de una review fuera del resultado filtrado | Se limpio la seleccion al aplicar `estado=nueva` | PASS |
| Tenant vacio / sin coincidencias / error de comunicacion | Tres estados distinguibles | Mensaje de tenant sin reviews, mensaje de no coincidencias y alerta de carga tras abortar una request en el navegador, respectivamente | PASS |
| Escritura rapida / solicitudes solapadas | Debounce cercano a 400 ms; cancelar respuesta anterior y no reemplazar resultados nuevos | Una request tras seis cambios rapidos; request anterior cancelada y respuesta vieja sin efecto | PASS |

Ejemplos observados en las requests reales:

```text
GET /api/v1/reviews?busqueda=servicio&estado=nueva
GET /api/v1/reviews?puntuacion=5&fuente=Google
GET /api/v1/reviews?busqueda=servicio&fecha_desde=2026-09-20&fecha_hasta=2026-09-20&puntuacion=5&estado=nueva&fuente=Google
```

Los parametros vacios se omitieron. El frontend no filtro `items` localmente ni envio `tenant_id`.

## Aislamiento y autorizacion

| Caso | Esperado | Obtenido | Estado |
|---|---|---|---|
| Tenant A busca contenido exclusivo de B | Sin reviews de B | `total=0`, tambien con seis criterios combinados | PASS |
| Tenant B busca contenido exclusivo de A | Sin reviews de A | `total=0` | PASS |
| Cliente agrega `tenant_id` manualmente | No cambia el tenant autorizado | A y B conservaron sus propios resultados | PASS |
| Usuario autenticado con tenant | Acceso al listado | 200 y solo reviews de su tenant | PASS |
| Solicitud sin autenticacion | Rechazo | HTTP 401 | PASS |
| Usuario autenticado sin tenant permitido | Rechazo | HTTP 403 | PASS |

## Regresiones de reviews

| Funcionalidad | Esperado | Obtenido | Estado |
|---|---|---|---|
| HU-06: registro manual | La nueva review aparece al volver al listado | POST 201; total del Tenant A de 7 a 8; busqueda la encuentra | PASS |
| HU-08: edicion | Al cambiar puntuacion, el filtro activo vuelve a consultar | PATCH 200; la review desaparecio de `puntuacion=4` tras pasar a 2 | PASS |
| HU-09: cambio de estado | El filtro activo refleja el nuevo estado | PATCH 200; desaparecio de `nueva` y aparecio en `en_revision` | PASS |

## Responsive e incidencias

| Viewport | Ancho global obtenido | Tabla y controles | Estado |
|---|---:|---|---|
| 375 px | 375 px | Seis columnas; scroll interno de tabla; busqueda, filtros, detalle y acciones visibles | PASS |
| 768 px | 768 px | Seis columnas; scroll interno de tabla; controles y acciones visibles | PASS |
| 1280 px | 1280 px | Sin desbordamiento global ni regresion | PASS |

- **Bug academico de fecha:** "El filtro de fecha excluye reviews del dia final del rango". **NO REPRODUCIDO**: se incluyo correctamente la review del ultimo microsegundo de `fecha_hasta`. No fue un bug real encontrado en la implementacion actual.
- **Bug real detectado durante TASK #3335:** desbordamiento horizontal de la vista de reviews en pantallas pequenas. El ancho intrinseco de la tabla expandia el item del grid. **CORREGIDO** con `min-w-0` en la seccion del listado, commit `2c86f405a99e179d2302005974d4bfea289fc044`. La pagina ya no supera el viewport; el scroll queda dentro de la tabla.
- No se encontraron bugs funcionales adicionales en la regresion final.

## Validaciones tecnicas

| Comando | Resultado |
|---|---|
| `python -m pytest` (backend) | 346 passed; 2 warnings de deprecacion conocidos de Starlette/httpx/anyio |
| `python -m compileall app` (backend) | OK |
| `node node_modules/eslint/bin/eslint.js .` (frontend) | OK |
| `node node_modules/vite/bin/vite.js build` (frontend) | OK |
| `git diff --check` | OK |

`npm` no estaba disponible en PATH; lint y build se ejecutaron mediante Node. El commit de esta TASK contiene solo esta evidencia documental. HU-10 queda tecnicamente completa en sus ocho TASK, pendiente de auditoria final antes de publicar la rama o crear un PR.
