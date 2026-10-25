import { useEffect, useRef, useState } from 'react'
import { FileText, LoaderCircle } from 'lucide-react'

import { generateReviewSummary } from '../../services/reviewService.js'
import AnalysisFeedback from './AnalysisFeedback.jsx'


function summaryError(error) {
  if (!error.response) {
    return 'No pudimos confirmar el resultado. Actualiza la review antes de volver a intentarlo.'
  }
  const messages = {
    401: 'Tu sesión expiró. Inicia sesión nuevamente.',
    403: 'No tienes permiso para generar el resumen de esta review.',
    404: 'La review ya no está disponible. Actualiza la lista.',
    409: 'El comentario cambió durante el análisis. Actualiza la review y vuelve a intentarlo.',
    422: 'El contenido de esta review no permite generar un resumen.',
    500: 'No se pudo guardar el resumen. Inténtalo más tarde.',
    502: 'No se obtuvo un resumen válido. Inténtalo de nuevo.',
    503: 'El servicio de resumen no está disponible en este momento. Inténtalo más tarde.',
    504: 'El servicio tardó demasiado en responder. Inténtalo más tarde.',
  }
  return messages[error.response.status] || 'No fue posible generar el resumen. Inténtalo más tarde.'
}


function ReviewSummary({ review, onSaved, onBusyChange, disabled = false }) {
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
      const updated = await generateReviewSummary(review.id, { signal: controller.signal })
      if (!controller.signal.aborted) {
        onSaved(updated)
        setSucceeded(true)
      }
    } catch (caught) {
      if (!controller.signal.aborted && caught.code !== 'ERR_CANCELED') {
        setError(summaryError(caught))
      }
    } finally {
      if (!controller.signal.aborted) {
        request.current = null
        setIsGenerating(false)
      }
    }
  }

  return (
    <section aria-label="Resumen automático" className="rounded-lg border border-sky-100 bg-sky-50/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <FileText aria-hidden="true" size={17} />
          Resumen automático
        </h3>
        <button
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-sky-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-sky-800 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled || isGenerating}
          onClick={handleGenerate}
          type="button"
        >
          {isGenerating && <LoaderCircle aria-hidden="true" className="motion-safe:animate-spin" size={16} />}
          {isGenerating ? 'Generando…' : review.resumen ? 'Regenerar resumen' : 'Generar resumen'}
        </button>
        {review.resumen && <span className="rounded-full bg-sky-100 px-2 py-1 text-xs font-medium text-sky-800">Generado por IA</span>}
      </div>
      <div aria-live="polite" aria-busy={isGenerating}>
        {review.resumen ? (
          <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-5 text-slate-700">{review.resumen}</p>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Esta review todavía no tiene un resumen.</p>
        )}
      </div>
      <AnalysisFeedback loading={isGenerating} succeeded={succeeded} loadingText="Generando resumen… Puede tardar unos segundos." successText="Resumen generado y guardado." />
      {error && <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
      <details className="mt-2 text-xs text-slate-500"><summary className="cursor-pointer">Sobre este resumen</summary><p className="mt-1 leading-5">Verifica el resumen con el comentario original. Si corriges el comentario, vuelve a generar el resumen.</p></details>
    </section>
  )
}

export default ReviewSummary
