import apiClient from './apiClient.js'

export async function listBusinesses({ signal } = {}) {
  const { data } = await apiClient.get('/tenants', { signal })
  return data.items
}

export async function getBusinessConnections(tenantId, { signal } = {}) {
  const { data } = await apiClient.get('/admin/google-connections', { params: { tenant_id: tenantId }, signal })
  return data
}

export async function createBusinessAccount(payload) {
  const { data } = await apiClient.post('/admin/business-accounts', payload, { timeout: 45000 })
  return data
}

export async function linkGoogleBusiness(payload) {
  const { data } = await apiClient.post('/admin/google-connections', payload, { timeout: 45000 })
  return data
}

export async function setGoogleConnection(payload) {
  const { data } = await apiClient.patch('/admin/google-connections', payload)
  return data
}
