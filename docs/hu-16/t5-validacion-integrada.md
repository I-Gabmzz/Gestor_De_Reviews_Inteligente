# HU-16 / T5 #3809: validación integrada y muestra real

Responsable: David Escárcega Schlemmer.
[Tarea #3809](https://computacion.mxl.uabc.mx/openproject/work_packages/3809).
Validación técnica: 25 de octubre de 2026, America/Tijuana.
La aceptación final del Product Owner permanece pendiente.

## Resultado de la muestra real

Se ejecutó `backend/scripts/verify_priority_t5.py` con el proveedor real Google
Gemini y el modelo solicitado `gemini-3.5-flash-lite`, reutilizando el adaptador
de la aplicación. Se utilizaron autenticación HTTP, servicio, repositorio y SQLite
temporal con reseñas sintéticas; no se modificó la base de demostración en esa
ejecución. El [reporte completo](validacion-t5-2026-10-25.json) conserva entradas,
expectativas, resultados, estados HTTP y comprobaciones de persistencia, sin
claves, tokens ni contraseñas.

- **16/16 casos de aceptación coincidentes**: cuatro Alta, tres Media, seis Baja
  y tres rechazos de contenido no analizable.
- **15 llamadas reales al proveedor**: el contenido vacío se rechazó antes de
  crearlo; las otras dos entradas no analizables produjeron rechazo controlado.
- **6/6 controles de acceso y entrada aprobados**, sin llamadas al proveedor:
  falta de token, administrador general, review ajena, ID inexistente, prioridad
  manual y tenant en el cuerpo.
- Detalle y listado HTTP coincidieron con la base de datos después de cada caso.
  Se conservaron otros campos, la review del otro negocio y la prioridad anterior
  ante un rechazo. Se alternaron los roles usuario de negocio y administrador de
  tenant para las solicitudes permitidas.

La muestra cubre cobro pendiente, casos mixtos, servicio pagado bloqueado,
insatisfacción sin urgencia sustentada, consultas, sugerencias, elogios, problema
resuelto, hecho negado e instrucciones dentro del comentario. Es una muestra de
aceptación que contiene ejemplos de la rúbrica y del prompt; no es un benchmark
independiente ni permite afirmar precisión general del 100 %.

## Demostración en la web local

Se reinició únicamente el backend local para cargar la ruta de prioridad. Se
preparó una nueva review sintética sin modificar las nueve existentes:

| Dato | Valor observado |
| --- | --- |
| Autor | Demostración HU-16 |
| Contenido | Me cobraron dos veces y nadie me responde. |
| Puntuación | 5/5 |
| Estado inicial y posterior | Nueva |
| Prioridad inicial | Sin determinar |
| Resultado desde el botón del panel | Alta |
| Resultado después de recargar | Alta, tanto en detalle como en la fila |

La operación se solicitó desde la pestaña Prioridad con administrador de negocio.
Se observó carga y bloqueo de edición/seguimiento, confirmación de guardado y la
marca accesible de Alta. La puntuación alta no impidió identificar el problema
grave descrito en el texto. La prioridad permaneció de solo lectura y el estado
no cambió automáticamente. La captura de la demostración se conserva localmente;
no se publica la base de datos ni la configuración del entorno.

## Regresión y reproducción

La suite completa local pasó **842 pruebas backend**, incluidas tres comprobaciones
del verificador que detectan resultados discrepantes, preservan los archivos de
resultados y evitan exponer credenciales. También pasaron **51 pruebas frontend**,
lint y compilación de producción. Se conserva el aviso previo de deprecación de
Starlette/httpx. Las comprobaciones remotas se ejecutan en el PR de HU-16; su estado
se registra por separado y no se deduce de las pruebas locales.

Para repetir la muestra autorizada desde `backend/`, con la credencial únicamente
en el entorno local y una ruta nueva de resultados:

```bash
.venv/bin/python scripts/verify_priority_t5.py --interval-seconds 6 --output /tmp/hu16-validacion-nueva.json
```

La ejecución puede consumir cuota. El script no se ejecuta como parte de pytest,
no reintenta automáticamente y se detiene ante un error de servicio. Un caso
fallido se conserva como tal y hace que la ejecución termine con código distinto
de cero. `--case` permite repetir casos concretos en otro archivo sin reemplazar
el reporte original.

## Pendiente de aceptación

El PO debe revisar la demostración y aceptar el comportamiento. No se registra
una aprobación ni un cierre de HU-16 en nombre del PO antes de recibirla. Esta
entrega no implementa las notificaciones de HU-20 ni acredita una integración en
main antes de revisar e integrar el PR correspondiente.
