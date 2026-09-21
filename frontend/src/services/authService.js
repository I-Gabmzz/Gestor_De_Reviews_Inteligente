import apiClient from './apiClient.js'

const ACCESS_TOKEN_KEY = 'gestor_reviews_access_token'
const USER_KEY = 'gestor_reviews_user'

function createAuthError(message, code) {
  const error = new Error(message)
  error.code = code
  return error
}

function getErrorMessage(error) {
  if (!error.response) {
    return createAuthError(
      'No pudimos conectar con el servidor. Verifica tu conexión e inténtalo de nuevo.',
      'NETWORK_ERROR',
    )
  }

  const { status, data } = error.response
  const detail = typeof data?.detail === 'string' ? data.detail.toLowerCase() : ''

  if (status === 401 || detail.includes('credenciales')) {
    return createAuthError('El correo o la contraseña son incorrectos.', 'INVALID_CREDENTIALS')
  }

  if (status === 403 && detail.includes('inactivo')) {
    return createAuthError(
      'Tu usuario está inactivo. Contacta al administrador de tu negocio.',
      'INACTIVE_USER',
    )
  }

  if (status >= 500) {
    return createAuthError(
      'No pudimos completar la autenticación. Inténtalo de nuevo más tarde.',
      'SERVER_ERROR',
    )
  }

  return createAuthError('No pudimos iniciar sesión. Revisa los datos e inténtalo de nuevo.', 'AUTH_ERROR')
}

function getStoredUser(responseUser) {
  return {
    id: responseUser.id,
    nombre: responseUser.nombre ?? null,
    correo: responseUser.correo,
    rol: responseUser.rol,
    tenant_id: responseUser.tenant_id,
  }
}

export async function login(credentials) {
  try {
    const { data } = await apiClient.post('/auth/login', {
      correo: credentials.correo,
      password: credentials.password,
    })

    if (!data?.access_token || !data?.user) {
      throw createAuthError(
        'No pudimos completar la autenticación. Inténtalo de nuevo más tarde.',
        'AUTH_ERROR',
      )
    }

    const user = getStoredUser(data.user)
    localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))

    return { access_token: data.access_token, user }
  } catch (error) {
    if (error.code === 'AUTH_ERROR') {
      throw error
    }

    throw getErrorMessage(error)
  }
}

export function getStoredSession() {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY)
  const storedUser = localStorage.getItem(USER_KEY)

  if (!accessToken || !storedUser) {
    return null
  }

  try {
    return { access_token: accessToken, user: JSON.parse(storedUser) }
  } catch {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    return null
  }
}
