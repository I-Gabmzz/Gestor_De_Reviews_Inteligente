export const ACCESS_TOKEN_KEY = 'gestor_reviews_access_token'
export const USER_KEY = 'gestor_reviews_user'
export const SESSION_ENDED_EVENT = 'gestor-reviews:session-ended'

export function logout() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
