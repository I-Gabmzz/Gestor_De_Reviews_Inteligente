import apiClient from './apiClient.js'

export async function getDashboard({ signal } = {}) {
  const { data } = await apiClient.get('/dashboard', { signal })
  return data
}
