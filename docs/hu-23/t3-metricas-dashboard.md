# HU-23 #4011 / T3 #4024 — Métricas del dashboard por negocio

## Contrato

El requisito del sprint es calcular los indicadores sobre todo el negocio autenticado. T3 implementa los nombres y la forma propuestos en [T1](./t1-contrato-urgencia-busqueda-metricas.md) y reutiliza la regla de [T2](./t2-busqueda-urgencia-paridad-csv.md). La ratificación externa de `urgente=true` antes de publicar sigue pendiente. No consta aprobación del PO.

`GET /api/v1/dashboard` conserva el alcance y la validación de tenant activo para `usuario_negocio` y `admin_tenant`. El cliente no elige el tenant ni restringe las métricas con filtros de bandeja.

| Campos | Comportamiento |
| --- | --- |
| `nombre_negocio`, `total_reviews`, `reviews_nuevas` | Campos existentes. El total cuenta filas y se conserva el tratamiento previo de mayúsculas para Nueva. |
| `promedio_puntuacion` | Media SQL de puntuaciones presentes como número sin redondeo de presentación. Es `null` si no hay puntuaciones. |
| `reviews_recientes` | Hasta cinco reseñas del tenant. Orden por fecha descendente y, en empate, por ID descendente. Conserva su esquema de lectura. |
| `reviews_en_revision`, `reviews_atendidas` | Conteos por estado `en_revision` y `atendida`. |
| `reviews_urgentes` | Prioridad `Alta` y estado `nueva` o `en_revision`. Comparte el predicado de listado y CSV. |
| `distribucion_puntuaciones` | Cinco objetos `{puntuacion, total}` en orden de 1 a 5, con ceros en las casillas sin coincidencias. |

Se usa una consulta agregada con `COUNT(*)`, `AVG` y conteos condicionales. La consulta de recientes se mantiene separada y ambas se limitan al tenant autenticado. Una puntuación ausente no suma al promedio ni a ninguna casilla, pero su fila sí cuenta para total, estado y urgencia según corresponda.

## Evidencia

- **Endpoint con esquema vigente.** Las pruebas usan dos negocios con reseñas parecidas, negocio vacío, puntuaciones repetidas y casillas vacías, promedio, permisos y recientes. Una transición real por `PATCH /api/v1/reviews/{id}/status` verifica el cambio de estados y urgencia, la estabilidad del promedio y la distribución, y la paridad con el listado `urgente=true` antes y después.
- **Agregación NULL aislada.** Las dos pruebas llaman al mismo método de repositorio que usa el dashboard. Usan una copia de la tabla en SQLite en memoria con puntuación nullable. Se verifica un negocio mixto y otro sin puntuaciones, ambos con una urgente sin puntuación. El modelo y las migraciones productivas no cambian.
- **Flujo integral pendiente de HU-24.** Su [contrato T1](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/blob/74149d6b5ee546d6cbff2e3686f275325fd5599b/docs/hu-24/t1-contrato-datos-opcionales.md) prevé datos opcionales. En esta rama `fecha` y `puntuacion` siguen con `nullable=False` y las recientes requieren ambas. Las pruebas de agregación no acreditan alta, persistencia ni lectura de recientes con nulos mediante la API ni certifican el esquema de una base personal o desplegada.

| Validación de T3 | Resultado |
| --- | --- |
| Backend `tests/test_dashboard.py` | 11 aprobadas, incluidas 2 de agregación aislada |
| Backend dirigido: listado, urgencia, CSV, cambio de estado, permisos y aislamiento | 309 aprobadas, 0 fallidas y 0 omitidas |
| Backend completo | 2079 aprobadas, 0 fallidas y 30 omitidas. Las 30 requieren TEST_POSTGRES_URL |
| Frontend dirigido: navegación y roles del dashboard | 7 aprobadas, 0 omitidas |
| Renderizado de `DashboardPage` con respuesta aditiva | Comprobación en memoria con JSDOM y adaptador HTTP simulado aprobada |
| Compilación del SQL de agregación y recientes | SQLite y PostgreSQL, sin conexión |

El backend se ejecutó con el intérprete aislado de T2, Python 3.14.4 con pytest 8.4.2 y `psycopg` 3.3.9. El ejecutor bloqueó HTTP externo y conexiones a la base de la aplicación, restringió SQLite a memoria o al directorio temporal y dejó `TEST_POSTGRES_URL` sin configurar. PostgreSQL real permanece sin verificar. ESLint, build y la suite frontend completa corresponden a la evidencia histórica de T2.

## Coordinación

David puede usar `reviews_en_revision`, `reviews_atendidas`, `reviews_urgentes` y `distribucion_puntuaciones` en T4 junto con los campos existentes. La interfaz y los enlaces quedan para esa tarea.

Al incorporar HU-24, revisar con José el alta, la persistencia y la consulta de una reseña reciente con fecha y puntuación ausentes, junto con una reseña puntuable. Comprobar el JSON, el orden de recientes según la decisión de fechas nulas y la exclusión de puntuaciones ausentes del promedio y de las estrellas. Repetir con un negocio con reseñas pero sin puntuaciones disponibles. Esta evidencia queda preparada para revisión.
