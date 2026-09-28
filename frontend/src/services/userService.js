import apiClient from './apiClient.js'

export async function getUsers({ signal } = {}) {
  const { data } = await apiClient.get('/users', { signal })
  return data
}
