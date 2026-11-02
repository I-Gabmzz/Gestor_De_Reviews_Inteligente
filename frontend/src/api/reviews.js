import apiClient from '../services/apiClient.js'


function reviewParams(criteria = {}) {
  const allowedCriteria = {
    busqueda: criteria.busqueda,
    fecha_desde: criteria.fecha_desde,
    fecha_hasta: criteria.fecha_hasta,
    puntuacion: criteria.puntuacion,
    estado: criteria.estado,
    fuente: criteria.fuente,
  }
  return Object.fromEntries(
    Object.entries(allowedCriteria)
      .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value])
      .filter(([, value]) => value !== '' && value != null),
  )
}


export async function getReviews(criteria = {}, options = {}) {
  const response = await apiClient.get('/reviews', { ...options, params: reviewParams(criteria) })
  return response.data
}


export async function exportReviews(criteria = {}) {
  const response = await apiClient.get('/reviews/export', {
    params: reviewParams(criteria),
    responseType: 'blob',
    timeout: 60000,
  })
  const contentType = response.headers?.['content-type']?.split(';')[0]?.trim().toLowerCase()
  const header = new TextEncoder().encode('\uFEFFid,contenido,autor,fecha,fuente,puntuacion,categoria,estado\r\n')
  const blob = response.data
  const prefix = blob instanceof Blob && blob.size >= header.length
    ? new Uint8Array(await blob.slice(0, header.length).arrayBuffer())
    : null
  if (contentType !== 'text/csv' || !prefix || header.some((byte, index) => byte !== prefix[index])) {
    const error = new Error('La respuesta de exportación no es un CSV válido.')
    error.code = 'INVALID_CSV_RESPONSE'
    throw error
  }
  return { blob, contentDisposition: response.headers?.['content-disposition'] }
}

export async function getReviewById(reviewId, options = {}) {
  const response = await apiClient.get(`/reviews/${reviewId}`, options)
  return response.data
}

export async function updateReview(reviewId, changes, options = {}) {
  const response = await apiClient.patch(`/reviews/${reviewId}`, changes, options)
  return response.data
}
