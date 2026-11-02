import { useEffect, useRef, useState } from 'react'
import { detectReviewTopic } from '../services/reviewService.js'

function topicErrorMessage(error) {
  const status = error.response?.status
  if (status === 401) return 'Tu sesión expiró. Inicia sesión nuevamente.'
  if (status === 403) return 'No tienes permiso para detectar el tema de esta review.'
  if (status === 404) return 'La review ya no está disponible. Actualiza la lista.'
  if (status === 409) return 'La review cambió durante el análisis. Actualízala y vuelve a intentarlo.'
  if (status === 422) return 'El contenido no permite identificar un único tema principal.'
  if (status === 502) return 'La IA no devolvió un tema válido. Puedes volver a intentarlo.'
  if (status === 503) return 'El servicio de IA no está disponible. Inténtalo más tarde.'
  if (status === 504 || error.code === 'ECONNABORTED') return 'El análisis tardó demasiado. Actualiza la review antes de volver a intentarlo.'
  return 'No fue posible completar la detección. Actualiza la review antes de volver a intentarlo.'
}

export default function useReviewTopic(review, onDetected) {
  const identity = JSON.stringify([review?.id, review?.tenant_id, review?.contenido])
  const pending = useRef(null)
  const [state, setState] = useState(null)

  useEffect(() => () => {
    pending.current?.controller.abort()
    pending.current = null
  }, [identity])

  async function detect() {
    if (!review || pending.current) return
    const request = { identity, controller: new AbortController() }
    pending.current = request
    setState({ identity, loading: true, error: '', succeeded: false })
    try {
      const result = await detectReviewTopic(review.id, { signal: request.controller.signal })
      if (request.controller.signal.aborted || pending.current !== request) return
      if (result.id !== review.id || result.tenant_id !== review.tenant_id || result.contenido !== review.contenido || typeof result.tema !== 'string' || !result.tema.trim()) {
        throw new Error('La respuesta no corresponde a la review analizada.')
      }
      onDetected(result)
      setState({ identity, loading: false, error: '', succeeded: true })
    } catch (error) {
      if (!request.controller.signal.aborted && pending.current === request) {
        setState({ identity, loading: false, error: topicErrorMessage(error) })
      }
    } finally {
      if (pending.current === request) pending.current = null
    }
  }

  return {
    detect,
    isDetecting: state?.identity === identity && state.loading,
    error: state?.identity === identity ? state.error : '',
    succeeded: state?.identity === identity && Boolean(state.succeeded),
  }
}
