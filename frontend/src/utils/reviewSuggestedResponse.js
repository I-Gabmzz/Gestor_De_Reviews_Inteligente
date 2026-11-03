export function matchesSuggestedResponse(review, result) {
  return Boolean(review && result && review.id === result.id
    && review.tenant_id === result.tenant_id && review.contenido === result.contenido
    && typeof result.respuesta_sugerida === 'string' && result.respuesta_sugerida.trim())
}

export function mergeSuggestedResponse(review, result) {
  return matchesSuggestedResponse(review, result)
    ? { ...review, respuesta_sugerida: result.respuesta_sugerida } : review
}

export function suggestedResponseError(error) {
  const messages = {
    401: 'Tu sesión expiró. Inicia sesión nuevamente.',
    403: 'No tienes permiso para generar esta sugerencia.',
    404: 'La review ya no está disponible. Actualiza la información.',
    409: 'La review o su sugerencia cambió. Recarga la información vigente antes de volver a intentarlo.',
    422: 'El contenido no permite generar una sugerencia segura.',
    500: 'No se pudo guardar la sugerencia. Recarga la información antes de reintentar.',
    502: 'La IA no devolvió una sugerencia válida. Puedes volver a intentarlo.',
    503: 'El servicio de IA no está disponible. Inténtalo más tarde.',
    504: 'La generación tardó demasiado. Recarga la información antes de reintentar.',
  }
  return messages[error.response?.status] || 'No pudimos confirmar la sugerencia. Recarga la información antes de reintentar.'
}
