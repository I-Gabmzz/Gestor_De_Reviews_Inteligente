import apiClient from './apiClient.js'

export async function getUsers({ signal } = {}) {
  const { data } = await apiClient.get('/users', { signal })
  return data
}

export async function createUser({ nombre, correo, password }) {
  const { data } = await apiClient.post('/users', { nombre, correo, password })
  return data
}

export async function updateUser(userId, changes) {
  const { data } = await apiClient.patch(`/users/${userId}`, changes)
  return data
}
