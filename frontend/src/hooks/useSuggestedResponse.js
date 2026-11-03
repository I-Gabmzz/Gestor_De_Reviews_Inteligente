import { useEffect, useRef, useState } from 'react'
import { generateSuggestedResponse } from '../services/reviewService.js'
import { matchesSuggestedResponse, suggestedResponseError } from '../utils/reviewSuggestedResponse.js'

export default function useSuggestedResponse(review, onSuggested) {
  const identity = JSON.stringify([review?.id, review?.tenant_id, review?.contenido])
  const activeRequest = useRef(null)
  const [operation, setOperation] = useState({ identity })

  // Ajustar el estado al cambiar de selección descarta también visitas anteriores.
  // La condición converge en el siguiente render, sin esperar un efecto posterior.
  if (operation.identity !== identity) {
    setOperation({ identity })
  }

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
  }, [identity])

  async function generate() {
    if (!review || activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    setOperation({ identity, loading: true, error: '', succeeded: false, conflict: false })
    try {
      const result = await generateSuggestedResponse(review.id, { signal: controller.signal })
      if (controller.signal.aborted || activeRequest.current !== controller) return
      if (!matchesSuggestedResponse(review, result)) throw new Error('Respuesta sugerida inválida')
      onSuggested(result)
      setOperation({ identity, loading: false, error: '', succeeded: true })
    } catch (error) {
      if (!controller.signal.aborted && activeRequest.current === controller) {
        setOperation({ identity, loading: false, error: suggestedResponseError(error), succeeded: false, conflict: error.response?.status === 409 })
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null
    }
  }

  function reset() {
    activeRequest.current?.abort()
    activeRequest.current = null
    setOperation({ identity })
  }

  const current = operation?.identity === identity ? operation : null
  return { generate, reset, isGenerating: Boolean(current?.loading), error: current?.error || '', succeeded: Boolean(current?.succeeded), conflict: Boolean(current?.conflict) }
}
