import apiClient from './apiClient.js'

export { exportReviews, getReviewById, getReviews, updateReview } from '../api/reviews.js'

export async function createReview(review) {
  const { data, status } = await apiClient.post('/reviews', review)
  if (status !== 201) {
    const error = new Error('La API no confirmó la creación de la review.')
    error.code = 'UNEXPECTED_CREATE_RESPONSE'
    throw error
  }
  return data
}

export async function updateReviewStatus(reviewId, estado) {
  const { data } = await apiClient.patch(`/reviews/${reviewId}/status`, { estado })
  return data
}

export async function classifyReview(reviewId, options = {}) {
  const { data } = await apiClient.post(`/reviews/${reviewId}/clasificacion`, undefined, {
    signal: options.signal,
    // El proveedor admite hasta 120 s; no cambiar el timeout de otras operaciones.
    timeout: 150000,
  })
  return data
}

export async function generateReviewSummary(reviewId, { signal } = {}) {
  // El proveedor admite hasta 120 s; el cliente deja margen para persistir.
  const { data } = await apiClient.post(`/reviews/${reviewId}/resumen`, {}, {
    signal,
    timeout: 135000,
  })
  return data
}

export async function detectReviewTopic(reviewId, options = {}) {
  const { data } = await apiClient.post(`/reviews/${reviewId}/tema`, undefined, {
    signal: options.signal,
    timeout: 150000,
  })
  return data
}
