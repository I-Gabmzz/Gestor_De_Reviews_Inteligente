const categories = ['Queja', 'Sugerencia', 'Felicitación', 'Consulta']

export function canClassifyReview(session) {
  return Boolean(session?.access_token && session.user?.tenant_id != null
    && ['usuario_negocio', 'admin_tenant'].includes(session.user.rol))
}

export function matchesClassification(review, result) {
  return Boolean(review && result && review.id === result.id
    && review.tenant_id === result.tenant_id && review.contenido === result.contenido
    && categories.includes(result.categoria))
}

export function mergeClassification(review, result) {
  return matchesClassification(review, result) ? { ...review, categoria: result.categoria } : review
}

export function classificationErrorMessage(error) {
  const status = error.response?.status
  if (status === 401) return 'Tu sesión expiró. Inicia sesión nuevamente para clasificar.'
  if (status === 403) return 'No tienes permiso para clasificar esta review.'
  if (status === 404) return 'La review ya no está disponible. Actualiza la lista.'
  if (status === 409) return 'El contenido cambió durante el análisis. Actualiza la review y vuelve a intentarlo.'
  if (status === 422) return 'El contenido no permite determinar una categoría. Revisa la review antes de volver a intentarlo.'
  if (status === 502) return 'La IA devolvió una respuesta no válida. Puedes volver a intentarlo.'
  if (status === 503) return 'El servicio de clasificación no está disponible. Inténtalo más tarde.'
  if (status === 504 || error.code === 'ECONNABORTED') return 'La clasificación tardó demasiado. Actualiza la review antes de volver a intentarlo.'
  if (!error.response) return 'No pudimos confirmar la clasificación. Verifica tu conexión y actualiza la review antes de volver a intentarlo.'
  return 'No fue posible guardar la clasificación. Puedes volver a intentarlo.'
}
