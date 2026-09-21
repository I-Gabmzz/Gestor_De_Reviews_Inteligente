import apiClient from './apiClient.js'

export async function getDashboard() {
  const { data } = await apiClient.get('/dashboard')
  return data
}
