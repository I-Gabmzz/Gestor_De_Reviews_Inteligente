import apiClient from '../services/apiClient.js'


export async function getReviews(criteria = {}, options = {}) {
  const allowedCriteria = {
    busqueda: criteria.busqueda,
    fecha_desde: criteria.fecha_desde,
    fecha_hasta: criteria.fecha_hasta,
    puntuacion: criteria.puntuacion,
    estado: criteria.estado,
    fuente: criteria.fuente,
  }
  const params = Object.fromEntries(
    Object.entries(allowedCriteria)
      .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value])
      .filter(([, value]) => value !== '' && value != null),
  )
  const response = await apiClient.get('/reviews', { ...options, params })
  return response.data
}

export async function getReviewById(reviewId, options = {}) {
  const response = await apiClient.get(`/reviews/${reviewId}`, options)
  return response.data
}

export async function updateReview(reviewId, changes, options = {}) {
  const response = await apiClient.patch(`/reviews/${reviewId}`, changes, options)
  return response.data
}
