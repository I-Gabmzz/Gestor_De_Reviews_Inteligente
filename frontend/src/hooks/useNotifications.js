import { useCallback, useEffect, useRef, useState } from 'react'
import { getNotifications } from '../services/notificationService.js'

function errorMessage(error) {
  if (error.response?.status === 401) return 'Tu sesión expiró. Inicia sesión nuevamente.'
  if (error.response?.status === 403) return 'Tu cuenta ya no tiene acceso a estos avisos.'
  return 'No pudimos actualizar los avisos. Inténtalo nuevamente.'
}

export default function useNotifications(user, enabled) {
  const scope = JSON.stringify([user?.id, user?.tenant_id, user?.rol])
  const request = useRef(null)
  const [state, setState] = useState(null)

  const load = useCallback(async (offset = 0) => {
    if (!enabled) return
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setState((previous) => ({ ...(previous?.scope === scope ? previous : { items: [], total: 0 }), scope, loading: true, error: '' }))
    try {
      const data = await getNotifications({ signal: controller.signal, offset })
      if (controller.signal.aborted || request.current !== controller) return
      setState({ ...data, scope, offset, loading: false, error: '' })
    } catch (error) {
      if (controller.signal.aborted || request.current !== controller) return
      const denied = [401, 403].includes(error.response?.status)
      setState((previous) => ({
        ...(previous?.scope === scope && !denied ? previous : { items: [], total: 0 }),
        scope, loading: false, error: errorMessage(error),
      }))
    } finally {
      if (request.current === controller) request.current = null
    }
  }, [enabled, scope])

  useEffect(() => {
    if (!enabled) return undefined
    const refresh = () => load(0)
    refresh()
    const timer = window.setInterval(refresh, 30000)
    window.addEventListener('focus', refresh)
    window.addEventListener('review-priority-saved', refresh)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', refresh)
      window.removeEventListener('review-priority-saved', refresh)
      request.current?.abort()
      request.current = null
    }
  }, [enabled, load])

  const current = state?.scope === scope ? state : { items: [], total: 0, offset: 0, loading: false, error: '' }
  return { ...current, load }
}
