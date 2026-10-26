import { useEffect, useRef, useState } from 'react'
import { FileText, LoaderCircle } from 'lucide-react'

import { generateReviewSolution } from '../../services/reviewService.js'
import AnalysisFeedback from './AnalysisFeedback.jsx'


function solutionError(error) {
  if (!error.response) {
    return 'No pudimos confirmar el resultado. Actualiza la review antes de volver a intentarlo.'
  }
  const messages = {
    401: 'Tu sesión expiró. Inicia sesión nuevamente.',
    403: 'No tienes permiso para generar la solución de esta review.',
    404: 'La review ya no está disponible. Actualiza la lista.',
    409: 'El comentario cambió durante el análisis. Actualiza la review y vuelve a intentarlo.',
    422: 'El contenido de esta review no permite generar una solución.',
    500: 'No se pudo guardar la solución. Inténtalo más tarde.',
    502: 'No se obtuvo una solución válida. Inténtalo de nuevo.',
    503: 'El servicio de solución no está disponible en este momento. Inténtalo más tarde.',
    504: 'El servicio tardó demasiado en responder. Inténtalo más tarde.',
  }
  return messages[error.response.status] || 'No fue posible generar la solución. Inténtalo más tarde.'
}


function ReviewSolution({ review, onSaved, onBusyChange, disabled = false }) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState('')
  const [succeeded, setSucceeded] = useState(false)
  const request = useRef(null)

  useEffect(() => () => request.current?.abort(), [])
  useEffect(() => {
    onBusyChange?.(isGenerating)
    return () => onBusyChange?.(false)
  }, [isGenerating, onBusyChange])

  async function handleGenerate() {
    if (disabled || request.current) return
    const controller = new AbortController()
    request.current = controller
    setIsGenerating(true)
    setError('')
    setSucceeded(false)
    try {
      const updated = await generateReviewSolution(review.id, { signal: controller.signal })
      if (!controller.signal.aborted) {
        onSaved(updated)
        setSucceeded(true)
      }
    } catch (caught) {
      if (!controller.signal.aborted && caught.code !== 'ERR_CANCELED') {
        setError(solutionError(caught))
      }
    } finally {
      if (!controller.signal.aborted) {
        request.current = null
        setIsGenerating(false)
      }
    }
  }

  return (
    <section aria-label="Posible solución" className="rounded-lg border border-sky-100 bg-sky-50/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <FileText aria-hidden="true" size={17} />
          Posible solución
        </h3>
        <button
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-sky-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-sky-800 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled || isGenerating}
          onClick={handleGenerate}
          type="button"
        >
          {isGenerating && <LoaderCircle aria-hidden="true" className="motion-safe:animate-spin" size={16} />}
          {isGenerating ? 'Generando…' : review.solucion ? 'Regenerar solución' : 'Generar solución'}
        </button>
        {review.solucion && <span className="rounded-full bg-sky-100 px-2 py-1 text-xs font-medium text-sky-800">Sugerencia de IA</span>}
      </div>
      <div aria-live="polite" aria-busy={isGenerating}>
        {review.solucion ? (
          <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-5 text-slate-700">{review.solucion}</p>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Esta review todavía no tiene una solución sugerida.</p>
        )}
      </div>
      <AnalysisFeedback loading={isGenerating} succeeded={succeeded} loadingText="Generando solución… Puede tardar unos segundos." successText="Solución generada y guardada." />
      {error && <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
      <details className="mt-2 text-xs text-slate-500"><summary className="cursor-pointer">Sobre esta solución</summary><p className="mt-1 leading-5">Revisa la propuesta antes de aplicarla. Generarla no ejecuta acciones ni cambia el estado de la review. Si cambia el comentario, debes generar otra solución.</p></details>
    </section>
  )
}

export default ReviewSolution
