import { useId, useState } from 'react'
import { CalendarDays, MessageSquareText, Pencil, Star } from 'lucide-react'
import ReviewStatusControl from './ReviewStatusControl.jsx'
import ReviewClassification from './ReviewClassification.jsx'
import ReviewSummary from './ReviewSummary.jsx'
import ReviewSolution from './ReviewSolution.jsx'
import AnalysisFeedback from './AnalysisFeedback.jsx'
import useReviewTopic from '../../hooks/useReviewTopic.js'
import useReviewClassification from '../../hooks/useReviewClassification.js'


const analysisTabs = [
  { key: 'clasificacion', label: 'Clasificación' },
  { key: 'resumen', label: 'Resumen' },
  { key: 'tema', label: 'Tema' },
  { key: 'solucion', label: 'Solución' },
]

const dateFormatter = new Intl.DateTimeFormat('es-MX', {
  dateStyle: 'long',
  timeStyle: 'short',
})

function DetailItem({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-900">{value || 'Sin información'}</dd>
    </div>
  )
}

function ReviewDetail({ review, isLoading, isStatusSaving, onEdit, onStatusConfirm, statusError, canClassify = false, onClassified, onSummarySaved, onSolutionSaved, canDetectTopic = false, onTopicDetected }) {
  const [activeTab, setActiveTab] = useState('clasificacion')
  const [isSummaryGenerating, setIsSummaryGenerating] = useState(false)
  const [isSolutionGenerating, setIsSolutionGenerating] = useState(false)
  const analysisId = useId()
  const classification = useReviewClassification(isLoading ? null : review, onClassified)
  const topic = useReviewTopic(isLoading ? null : review, onTopicDetected)
  const busy = classification.isClassifying || topic.isDetecting || isSummaryGenerating || isSolutionGenerating

  function handleTabKeyDown(event, index) {
    const offsets = { ArrowRight: 1, ArrowLeft: -1 }
    let next
    if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = analysisTabs.length - 1
    else if (event.key in offsets) next = (index + offsets[event.key] + analysisTabs.length) % analysisTabs.length
    else return
    event.preventDefault()
    setActiveTab(analysisTabs[next].key)
    event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next]?.focus()
  }

  if (isLoading) {
    return (
      <aside className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:sticky xl:top-4" aria-live="polite">
        <div className="h-5 w-36 animate-pulse rounded bg-slate-200" />
        <div className="mt-6 space-y-3">
          <div className="h-4 animate-pulse rounded bg-slate-100" />
          <div className="h-4 animate-pulse rounded bg-slate-100" />
          <div className="h-4 w-4/5 animate-pulse rounded bg-slate-100" />
        </div>
      </aside>
    )
  }

  if (!review) {
    return (
      <aside className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
        Selecciona una review para consultar sus detalles.
      </aside>
    )
  }

  return (
    <aside className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:sticky xl:top-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Detalle de review</p>
          <h2 className="mt-1 text-xl font-semibold text-slate-900">{review.autor || 'Cliente anónimo'}</h2>
        </div>
        <span className="inline-flex items-center gap-1 rounded-lg bg-amber-50 px-2.5 py-1.5 font-semibold text-amber-700">
          <Star aria-hidden="true" className="fill-amber-400 text-amber-400" size={17} />
          {review.puntuacion}
        </span>
      </div>

      <div className="mt-2 flex items-center gap-2 text-sm text-slate-500">
        <CalendarDays aria-hidden="true" size={16} />
        <time dateTime={review.fecha}>{dateFormatter.format(new Date(review.fecha))}</time>
      </div>

      <div className="mt-3 rounded-lg bg-slate-50 p-3">
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
          <MessageSquareText aria-hidden="true" size={17} />
          Comentario
        </div>
        <p className="max-h-32 overflow-y-auto whitespace-pre-wrap text-sm leading-5 text-slate-700">{review.contenido}</p>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-3 border-t border-slate-100 pt-3">
        <DetailItem label="Fuente" value={review.fuente} />
        <DetailItem label="Categoría" value={review.categoria} />
        <DetailItem label="Prioridad" value={review.prioridad} />
      </dl>
      <div className="mt-3">
        <div role="tablist" aria-label="Análisis de la review" className="flex gap-1 rounded-full bg-slate-100 p-1">
          {analysisTabs.map((tab, index) => {
            const selected = activeTab === tab.key
            const pending = tab.key === 'clasificacion' ? classification.isClassifying : tab.key === 'tema' ? topic.isDetecting : tab.key === 'solucion' ? isSolutionGenerating : isSummaryGenerating
            return (
              <button
                key={tab.key}
                id={`${analysisId}-tab-${tab.key}`}
                role="tab"
                type="button"
                aria-selected={selected}
                aria-controls={`${analysisId}-panel-${tab.key}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setActiveTab(tab.key)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
                className={`inline-flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-full px-2 py-2 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 ${selected ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}
              >
                {tab.label}
                {pending && <span aria-label="En proceso" className="h-1.5 w-1.5 shrink-0 rounded-full bg-sky-600 motion-safe:animate-pulse" />}
              </button>
            )
          })}
        </div>
        <div role="tabpanel" id={`${analysisId}-panel-clasificacion`} aria-labelledby={`${analysisId}-tab-clasificacion`} hidden={activeTab !== 'clasificacion'} tabIndex={0} className="mt-3 focus-visible:outline-2 focus-visible:outline-sky-600">
          {!canClassify && <p className="text-sm text-slate-600">{review.categoria || 'Sin clasificar'}</p>}
          <ReviewClassification
            canClassify={canClassify}
            category={review.categoria}
            disabled={isStatusSaving || topic.isDetecting || isSummaryGenerating || isSolutionGenerating}
            error={classification.error}
            isClassifying={classification.isClassifying}
            onClassify={classification.classify}
            succeeded={classification.succeeded}
          />
        </div>
        <div role="tabpanel" id={`${analysisId}-panel-resumen`} aria-labelledby={`${analysisId}-tab-resumen`} hidden={activeTab !== 'resumen'} tabIndex={0} className="mt-3 focus-visible:outline-2 focus-visible:outline-sky-600">
          <ReviewSummary
            key={`${review.id}:${review.tenant_id}:${review.contenido}`}
            review={review}
            onSaved={onSummarySaved}
            onBusyChange={setIsSummaryGenerating}
            disabled={isStatusSaving || classification.isClassifying || topic.isDetecting || isSolutionGenerating}
          />
        </div>
        <div role="tabpanel" id={`${analysisId}-panel-tema`} aria-labelledby={`${analysisId}-tab-tema`} hidden={activeTab !== 'tema'} tabIndex={0} className="mt-3 focus-visible:outline-2 focus-visible:outline-sky-600">
          <section aria-label="Tema principal" aria-busy={Boolean(topic.isDetecting)} className="rounded-lg border border-slate-200 p-3">
            <h3 className="text-sm font-semibold text-slate-800">Tema principal</h3>
            <p aria-live="polite" className="mt-1 break-words text-sm text-slate-700">
              {review.tema || 'Sin detectar'}
            </p>
            {review.tema && <p className="mt-1 text-xs text-slate-500">Generado por IA</p>}
            {canDetectTopic && (
              <button
                className="mt-2 w-full rounded-lg border border-sky-300 px-3 py-2 text-sm font-semibold text-sky-800 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={topic.isDetecting || isStatusSaving || classification.isClassifying || isSummaryGenerating || isSolutionGenerating}
                onClick={topic.detect}
                type="button"
              >
                {topic.isDetecting ? 'Detectando tema…' : review.tema ? 'Actualizar tema' : 'Detectar tema'}
              </button>
            )}
            <AnalysisFeedback loading={topic.isDetecting} succeeded={topic.succeeded} loadingText="Detectando el tema… Puede tardar unos segundos." successText="Tema detectado y guardado." />
            {topic.error && <p className="mt-3 text-sm text-red-800" role="alert">{topic.error}</p>}
          </section>
        </div>
      </div>
      <div role="tabpanel" id={`${analysisId}-panel-solucion`} aria-labelledby={`${analysisId}-tab-solucion`} hidden={activeTab !== 'solucion'} tabIndex={0} className="mt-3 focus-visible:outline-2 focus-visible:outline-sky-600">
        <ReviewSolution
          key={`${review.id}:${review.tenant_id}:${review.contenido}`}
          review={review}
          onSaved={onSolutionSaved}
          onBusyChange={setIsSolutionGenerating}
          disabled={!canClassify || isStatusSaving || classification.isClassifying || topic.isDetecting || isSummaryGenerating}
        />
      </div>
      <fieldset disabled={busy}>
        <ReviewStatusControl
          disabled={busy}
          isSaving={isStatusSaving}
          key={`${review.id}:${review.estado}`}
          onConfirm={onStatusConfirm}
          status={review.estado}
        />
      </fieldset>
      {statusError && (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
          {statusError}
        </p>
      )}
      <button
        className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isStatusSaving || busy}
        onClick={() => onEdit(review)}
        type="button"
      >
        <Pencil aria-hidden="true" size={16} />
        Editar review
      </button>
    </aside>
  )
}

export default ReviewDetail
