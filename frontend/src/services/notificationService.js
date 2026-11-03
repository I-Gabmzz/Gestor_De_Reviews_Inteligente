import apiClient from './apiClient.js'

export const NOTIFICATION_PAGE_SIZE = 5

export async function getNotifications({ signal, offset = 0 } = {}) {
  const { data } = await apiClient.get('/notificaciones', {
    signal,
    params: { limit: NOTIFICATION_PAGE_SIZE, offset },
  })
  const validId = (value) => Number.isSafeInteger(value) && value > 0
  if (!data || !Array.isArray(data.items) || !Number.isSafeInteger(data.total) || data.total < 0 || data.total < data.items.length
    || data.items.some((item) => !item || !validId(item.id) || !validId(item.review_id)
      || typeof item.extracto !== 'string' || (item.autor !== null && typeof item.autor !== 'string')
      || typeof item.creada_en !== 'string' || !Number.isFinite(Date.parse(item.creada_en))
      || item.prioridad !== 'Alta')) {
    throw new Error('La respuesta de avisos no es válida.')
  }
  return data
}
