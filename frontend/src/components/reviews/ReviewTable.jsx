import { Star } from 'lucide-react'
import ReviewStatusBadge from './ReviewStatusBadge.jsx'


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
    <span className="line-clamp-2 break-words whitespace-normal text-slate-600" title={content}>
      {content}
    </span>
  )
}

function Rating({ value }) {
  return (
    <span className="inline-flex items-center gap-1 font-medium text-slate-800">
      <Star aria-hidden="true" className="fill-amber-400 text-amber-400" size={16} />
      {value}/5
    </span>
  )
}


function ReviewTable({ reviews, selectedReviewId, onSelect }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="ui-table review-table w-full table-fixed divide-y divide-slate-200 text-left text-sm">
          <colgroup>
            <col className="w-[17%]" />
            <col className="w-[24%]" />
            <col className="w-[15%]" />
            <col className="w-[12%]" />
            <col className="w-[14%]" />
            <col className="w-[18%]" />
          </colgroup>
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3 font-semibold" scope="col">Autor</th>
              <th className="px-5 py-3 font-semibold" scope="col">Resumen</th>
              <th className="px-5 py-3 font-semibold" scope="col">Fecha</th>
              <th className="px-5 py-3 font-semibold" scope="col">Fuente</th>
              <th className="px-5 py-3 font-semibold" scope="col">Puntuación</th>
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
                  <td className="break-words px-5 py-4 font-medium text-slate-900">
                    {review.autor || 'Anónimo'}
                  </td>
                  <td className="px-5 py-4"><Summary content={review.contenido} /></td>
                  <td className="px-5 py-4 text-slate-600">
                    {formatDate(review.fecha)}
                  </td>
                  <td className="break-words px-5 py-4 text-slate-600">{review.fuente}</td>
                  <td className="whitespace-nowrap px-5 py-4"><Rating value={review.puntuacion} /></td>
                  <td className="whitespace-nowrap px-5 py-4"><ReviewStatusBadge status={review.estado} /></td>
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
