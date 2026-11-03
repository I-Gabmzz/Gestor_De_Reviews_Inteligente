import apiClient from './apiClient.js'
import { parseExternalConnections, parseExternalImportResult } from '../utils/externalReviewImport.js'


export async function importReviews(file) {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await apiClient.post('/reviews/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return data
}

export async function getExternalReviewConnections({ signal } = {}) {
  const { data } = await apiClient.get('/integrations/google/reviews/connections', { signal })
  return parseExternalConnections(data)
}

export async function importExternalReviews(businessDataId, { signal } = {}) {
  const { data, status } = await apiClient.post('/integrations/google/reviews/import', {
    business_data_id: businessDataId,
  }, {
    signal,
    // Hasta cinco páginas y lecturas de 120 s; un timeout no confirma rollback.
    timeout: 720000,
  })
  if (status !== 200) throw new Error('La API no confirmó el resultado de la importación')
  return parseExternalImportResult(data)
}
