import { useEffect, useRef, useState } from 'react'
import { classifyReview } from '../services/reviewService.js'
import { classificationErrorMessage, matchesClassification } from '../utils/reviewClassification.js'

export default function useReviewClassification(review, onClassified) {
  const identity = JSON.stringify([review?.id, review?.tenant_id, review?.contenido])
  const activeRequest = useRef(null)
  const [operation, setOperation] = useState(null)

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
  }, [identity])

  async function classify() {
    if (!review || activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    setOperation({ identity, loading: true, error: '', succeeded: false })
    try {
      const result = await classifyReview(review.id, { signal: controller.signal })
      if (controller.signal.aborted || activeRequest.current !== controller) return
      if (!matchesClassification(review, result)) throw new Error('Respuesta de clasificación inválida')
      onClassified(result)
      setOperation({ identity, loading: false, error: '', succeeded: true })
    } catch (error) {
      if (!controller.signal.aborted && activeRequest.current === controller) {
        setOperation({ identity, loading: false, error: classificationErrorMessage(error), succeeded: false })
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null
    }
  }

  const current = operation?.identity === identity ? operation : null
  return { classify, isClassifying: Boolean(current?.loading), error: current?.error || '', succeeded: Boolean(current?.succeeded) }
}
