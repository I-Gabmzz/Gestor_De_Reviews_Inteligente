import { Star } from 'lucide-react'


const dateFormatter = new Intl.DateTimeFormat('es-MX', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

function formatDate(value) {
  return dateFormatter.format(new Date(value))
}

function Summary({ content }) {
  return (
    <span className="block max-w-xs truncate text-slate-600" title={content}>
      {content}
    </span>
  )
}

function Rating({ value }) {
  return (
    <span className="inline-flex items-center gap-1 font-medium text-slate-800">
      <Star aria-hidden="true" className="fill-amber-400 text-amber-400" size={16} />
      {value}
    </span>
  )
}

function StatusBadge({ value }) {
  const normalizedValue = value.toLowerCase()
  const colorClasses = {
    atendida: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    en_revision: 'bg-sky-50 text-sky-700 ring-sky-600/20',
    nueva: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  }
  const colorClass = colorClasses[normalizedValue]
    ?? 'bg-slate-100 text-slate-700 ring-slate-600/20'

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize ring-1 ring-inset ${colorClass}`}>
      {value.replaceAll('_', ' ')}
    </span>
  )
}

function ReviewTable({ reviews, selectedReviewId, onSelect }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3 font-semibold" scope="col">Autor</th>
              <th className="px-5 py-3 font-semibold" scope="col">Resumen</th>
              <th className="px-5 py-3 font-semibold" scope="col">Fecha</th>
              <th className="px-5 py-3 font-semibold" scope="col">Fuente</th>
              <th className="px-5 py-3 font-semibold" scope="col">Calificación</th>
              <th className="px-5 py-3 font-semibold" scope="col">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {reviews.map((review) => {
              const isSelected = review.id === selectedReviewId

              return (
                <tr
                  aria-selected={isSelected}
                  className={`cursor-pointer transition ${isSelected ? 'bg-sky-50' : 'hover:bg-slate-50'}`}
                  key={review.id}
                  onClick={() => onSelect(review.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      onSelect(review.id)
                    }
                  }}
                  tabIndex={0}
                >
                  <td className="whitespace-nowrap px-5 py-4 font-medium text-slate-900">
                    {review.autor || 'Anónimo'}
                  </td>
                  <td className="px-5 py-4"><Summary content={review.contenido} /></td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {formatDate(review.fecha)}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">{review.fuente}</td>
                  <td className="whitespace-nowrap px-5 py-4"><Rating value={review.puntuacion} /></td>
                  <td className="whitespace-nowrap px-5 py-4"><StatusBadge value={review.estado} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ReviewTable
