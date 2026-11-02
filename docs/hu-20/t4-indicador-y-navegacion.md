# HU-20 / T4 #3829: mostrar y abrir aviso

Responsable: David Escárcega Schlemmer.

El indicador de avisos aparece en la barra de sesión de los usuarios y
administradores del negocio. Consulta el total de reviews con un aviso de
prioridad Alta vigente; no representa mensajes no leídos. El administrador
general no consulta esta información.

El panel muestra autor, extracto, prioridad y fecha, con cinco avisos por página.
Incluye estados de carga, lista vacía, error y reintento. Se actualiza al guardar
una prioridad, al recuperar el foco y cada treinta segundos. Las solicitudes
anteriores se cancelan y sus respuestas se descartan al cambiar de cuenta o
negocio; una denegación de acceso limpia los datos anteriores.

Cada enlace abre la review indicada mediante su identificador. La página
descarta filtros que puedan ocultarla y consulta el detalle con la autorización
habitual del backend. Abrir el aviso no cambia el estado de seguimiento.
La selección se conserva al recargar la dirección. El panel admite cierre con
Escape, botón de cierre o clic fuera y ofrece etiquetas accesibles.

## Validación local

Comprobaciones realizadas el 2 de noviembre de 2026:

- Pasaron las 57 pruebas de frontend, incluidas seis pruebas de avisos que
  cubren consulta autenticada, contador, navegación exacta, carga, error,
  reintento, paginación, cambio de negocio y acceso denegado.
- Lint y compilación de producción finalizaron correctamente. Tras corregir
  el recorte del panel en ventanas estrechas, se repitieron las seis pruebas
  de avisos, lint y compilación.
- En la web local, actualizar la prioridad de la review sintética 205 produjo
  un aviso visible para Cafetería Horizonte. El enlace del dashboard abrió esa
  misma review y mantuvo su estado Nueva al abrirla y recargarla.
- La cuenta del segundo negocio no recibió ese aviso ni pudo leer su detalle.
- El panel quedó dentro de los límites de ventanas de 375, 508, 768 y 1100
  píxeles de ancho. Se restauró el tamaño normal del navegador al finalizar.

La validación completa de HU-20, CI e integración por PR corresponden a T5
#3830. Esta tarea entrega el indicador y la navegación de la interfaz.
