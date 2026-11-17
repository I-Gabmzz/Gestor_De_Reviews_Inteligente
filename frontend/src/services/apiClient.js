import axios from 'axios'
import { ACCESS_TOKEN_KEY, SESSION_ENDED_EVENT, logout } from './sessionStorage.js'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)

  if (token && config.url !== '/auth/login') {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

apiClient.interceptors.response.use(undefined, (error) => {
  const { config, response } = error
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token && config?.headers?.get('Authorization') === `Bearer ${token}`) {
    const detail = response?.data?.detail
    let reason
    if (response?.status === 401) reason = 'expired'
    if (response?.status === 403) {
      if (detail === 'El tenant está inactivo o no existe') reason = 'inactive-business'
      if (detail === 'El usuario está inactivo') reason = 'inactive-user'
    }
    if (reason) {
      logout()
      window.dispatchEvent(new window.CustomEvent(SESSION_ENDED_EVENT, { detail: reason }))
    }
  }
  return Promise.reject(error)
})

export default apiClient
