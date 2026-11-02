# HU-20 / T5 #3830: probar flujo Alta

Responsable: David Escárcega Schlemmer.
Validación realizada el 2 de noviembre de 2026.

## Resultado local

La versión validada integra los avisos de HU-20 con el main que ya incorpora
HU-19, incluida la exportación CSV. Se resolvió el conflicto de importaciones de
la pantalla de reviews conservando el icono de descarga y la navegación mediante
el identificador del aviso. Los cuatro commits anteriores de HU-20 se conservan.

- Backend: **947 pruebas aprobadas** y carga de la aplicación FastAPI correcta.
- Frontend: **65 pruebas aprobadas**, lint y compilación de producción correctos.
- Se añadieron **15 pruebas del flujo HTTP integrado**, con el transporte del
  proveedor simulado y la autenticación, servicios y persistencia reales.
- Gemini real: **9 comprobaciones aprobadas con 3 llamadas**, reseñas sintéticas
  y SQLite temporal. El resultado está en `validacion-t5-20261102.json`.

## Casos integrados

Las pruebas enlazan la generación y persistencia de prioridad con la consulta
del aviso y el detalle autorizado de la review. Cubren Alta y no Alta, reintentos,
cuatro solicitudes simultáneas, ciclo Alta/Media/Alta, respuestas inválidas,
fallos de proveedor, errores de inserción y commit, cambio de contenido durante
el análisis y aislamiento entre negocios en ambos sentidos. La prioridad y el
aviso se revierten juntos ante un fallo de persistencia.

También se comprueba que el CSV conserve el contrato vigente de HU-19: ID,
contenido, autor, fecha, fuente, puntuación, categoría y estado. Generar prioridad
y avisos no altera esos campos ni incorpora columnas nuevas al archivo.

La comprobación con Gemini real verifica Alta, reintento con el mismo ID y fecha,
Baja sin aviso, lectura posterior sin cambios de seguimiento, aviso compartido
por los roles del negocio y denegación de acceso desde otra cuenta de negocio,
un administrador general o una sesión ausente. No utiliza la base de demostración.

## Demostración de interfaz

En la web local, el aviso del dashboard abre la review sintética 205 del negocio
de demostración. La prioridad sigue en Alta y el estado Nueva se conserva. La
pantalla integrada mantiene la acción de exportación CSV y el contador de avisos.
La prueba de cambio de negocio y la apertura de la review se realizaron también
en T4; no se modificaron los datos originales de esa demostración.

## Reproducción

Desde backend, ejecutar `python -m pytest` para la regresión. Para comprobar el
proveedor real, configurar localmente la credencial y ejecutar
`python scripts/verify_notifications_t5.py --output /tmp/hu20-nueva-validacion.json`.
El script exige un archivo nuevo y no guarda credenciales ni tokens en el reporte.

Desde frontend, ejecutar las pruebas de `tests/*.test.mjs`, lint y build. En Node
24 local se usa `--no-experimental-global-navigator`; la CI utiliza Node 20.

La CI del PR y la aceptación final del Product Owner deben quedar verificadas y
registradas en OpenProject antes de cerrar #3830 y HU-20. El correo y otros
canales externos no forman parte de esta primera versión de avisos internos.
