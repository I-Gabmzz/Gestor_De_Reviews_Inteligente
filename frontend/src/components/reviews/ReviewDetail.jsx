import { CalendarDays, MessageSquareText, Pencil, Star } from 'lucide-react'
import ReviewStatusControl from './ReviewStatusControl.jsx'
import ReviewClassification from './ReviewClassification.jsx'
import ReviewSummary from './ReviewSummary.jsx'
import useReviewTopic from '../../hooks/useReviewTopic.js'
import useReviewClassification from '../../hooks/useReviewClassification.js'


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

function ReviewDetail({ review, isLoading, isStatusSaving, onEdit, onStatusConfirm, statusError, canClassify = false, onClassified, onSummarySaved, canDetectTopic = false, onTopicDetected }) {
  const classification = useReviewClassification(isLoading ? null : review, onClassified)
  const topic = useReviewTopic(isLoading ? null : review, onTopicDetected)
  if (isLoading) {
    return (
      <aside className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" aria-live="polite">
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
    <aside className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
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

      <div className="mt-5 flex items-center gap-2 text-sm text-slate-500">
        <CalendarDays aria-hidden="true" size={16} />
        <time dateTime={review.fecha}>{dateFormatter.format(new Date(review.fecha))}</time>
      </div>

      <div className="mt-6 rounded-lg bg-slate-50 p-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
          <MessageSquareText aria-hidden="true" size={17} />
          Comentario
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{review.contenido}</p>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-5 border-t border-slate-100 pt-5">
        <DetailItem label="Fuente" value={review.fuente} />
        <DetailItem label="Categoría" value={review.categoria} />
        <DetailItem label="Prioridad" value={review.prioridad} />
      </dl>
      <ReviewClassification
        canClassify={canClassify}
        category={review.categoria}
        disabled={isStatusSaving || topic.isDetecting}
        error={classification.error}
        isClassifying={classification.isClassifying}
        onClassify={classification.classify}
        succeeded={classification.succeeded}
      />
      <ReviewSummary
        key={`${review.id}:${review.tenant_id}:${review.contenido}`}
        review={review}
        onSaved={onSummarySaved}
        disabled={isStatusSaving || classification.isClassifying || topic.isDetecting}
      />
      <section aria-label="Tema principal" className="mt-5 rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-semibold text-slate-800">Tema principal</h3>
        <p aria-live="polite" className="mt-2 break-words text-sm text-slate-700">
          {review.tema || 'Aún no se ha detectado un tema.'}
        </p>
        {review.tema && <p className="mt-1 text-xs text-slate-500">Generado por IA</p>}
        {canDetectTopic && (
          <button
            className="mt-3 w-full rounded-lg border border-sky-300 px-3 py-2 text-sm font-semibold text-sky-800 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={topic.isDetecting || isStatusSaving || classification.isClassifying}
            onClick={topic.detect}
            type="button"
          >
            {topic.isDetecting ? 'Detectando tema…' : review.tema ? 'Detectar tema nuevamente' : 'Detectar tema'}
          </button>
        )}
        {topic.isDetecting && <p className="mt-2 text-xs text-slate-500" role="status">Analizando el contenido de esta review…</p>}
        {topic.error && <p className="mt-3 text-sm text-red-800" role="alert">{topic.error}</p>}
      </section>
      <fieldset disabled={classification.isClassifying || topic.isDetecting}>
        <ReviewStatusControl
          disabled={classification.isClassifying || topic.isDetecting}
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
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isStatusSaving || classification.isClassifying || topic.isDetecting}
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
