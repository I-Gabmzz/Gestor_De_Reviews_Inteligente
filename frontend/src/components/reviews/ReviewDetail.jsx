import { CalendarDays, MessageSquareText, Star } from 'lucide-react'


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

function ReviewDetail({ review, isLoading }) {
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
        <DetailItem label="Estado" value={review.estado} />
        <DetailItem label="Categoría" value={review.categoria} />
        <DetailItem label="Prioridad" value={review.prioridad} />
      </dl>
    </aside>
  )
}

export default ReviewDetail
