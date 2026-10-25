import { useEffect, useRef, useState } from 'react'
import { prioritizeReview } from '../services/reviewService.js'
import { matchesPriority, priorityErrorMessage } from '../utils/reviewPriority.js'

export default function useReviewPriority(review, onPrioritized) {
  const identity = JSON.stringify([review?.id, review?.tenant_id, review?.contenido])
  const activeRequest = useRef(null)
  const [operation, setOperation] = useState(null)

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
  }, [identity])

  async function prioritize() {
    if (!review || activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    setOperation({ identity, loading: true, error: '', succeeded: false })
    try {
      const result = await prioritizeReview(review.id, { signal: controller.signal })
      if (controller.signal.aborted || activeRequest.current !== controller) return
      if (!matchesPriority(review, result)) throw new Error('Respuesta de prioridad inválida')
      onPrioritized(result)
      setOperation({ identity, loading: false, error: '', succeeded: true })
    } catch (error) {
      if (!controller.signal.aborted && activeRequest.current === controller) {
        setOperation({ identity, loading: false, error: priorityErrorMessage(error), succeeded: false })
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null
    }
  }

  const current = operation?.identity === identity ? operation : null
  return { prioritize, isPrioritizing: Boolean(current?.loading), error: current?.error || '', succeeded: Boolean(current?.succeeded) }
}
