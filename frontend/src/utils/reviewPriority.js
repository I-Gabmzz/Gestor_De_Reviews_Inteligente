import { canAccessRoute } from './roleAccess.js'

const priorities = ['Baja', 'Media', 'Alta']

export function canPrioritizeReview(session) {
  return Boolean(session?.access_token && session.user?.tenant_id != null
    && canAccessRoute(session.user.rol, '/reviews'))
}

export function matchesPriority(review, result) {
  return Boolean(review && result && review.id === result.id
    && review.tenant_id === result.tenant_id && review.contenido === result.contenido
    && priorities.includes(result.prioridad))
}

export function mergePriority(review, result) {
  return matchesPriority(review, result) ? { ...review, prioridad: result.prioridad } : review
}

export function priorityErrorMessage(error) {
  const status = error.response?.status
  if (status === 401) return 'Tu sesión expiró. Inicia sesión nuevamente para determinar la prioridad.'
  if (status === 403) return 'No tienes permiso para determinar la prioridad de esta review.'
  if (status === 404) return 'La review ya no está disponible. Actualiza la lista.'
  if (status === 409) return 'El contenido cambió durante el análisis. Actualiza la review y vuelve a intentarlo.'
  if (status === 422) return 'El contenido no permite determinar una prioridad. Revisa la review antes de volver a intentarlo.'
  if (status === 502) return 'La IA no devolvió una prioridad válida. Puedes volver a intentarlo.'
  if (status === 503) return 'El servicio de prioridad no está disponible. Inténtalo más tarde.'
  if (status === 504 || error.code === 'ECONNABORTED') return 'El análisis tardó demasiado. Actualiza la review antes de volver a intentarlo.'
  if (!error.response) return 'No pudimos confirmar la prioridad. Verifica tu conexión y actualiza la review antes de volver a intentarlo.'
  return 'No fue posible guardar la prioridad. Actualiza la review antes de volver a intentarlo.'
}
