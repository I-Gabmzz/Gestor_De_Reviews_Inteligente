import { useState } from 'react'
import { ReviewDate, ReviewRating, ReviewSource } from './ReviewMetadata.jsx'
import ReviewStatusBadge from './ReviewStatusBadge.jsx'
import ReviewPriorityBadge from './ReviewPriorityBadge.jsx'
import { REVIEW_STATUS } from '../../utils/reviewStatus.js'


function Summary({ content }) {
  return (
    <span className="line-clamp-2 break-words whitespace-normal text-slate-600" title={content}>
      {content}
    </span>
  )
}

function ReviewCard({ review, isSelected, onSelect }) {
  return (
    <li className="min-w-0">
      <button
        aria-current={isSelected ? 'true' : undefined}
        className={`review-card min-h-11 w-full min-w-0 border p-4 text-left text-slate-900 shadow-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 ${isSelected ? 'border-sky-500 bg-sky-50' : 'border-slate-200 bg-white hover:border-sky-300 active:bg-slate-50'}`}
        data-review-id={review.id}
        onClick={(event) => onSelect(review.id, event.currentTarget)}
        type="button"
      >
        <span className="flex min-w-0 flex-wrap items-start justify-between gap-2">
          <span className="min-w-0 break-words font-semibold text-slate-900">
            {review.autor || 'Sin autor'}
            {review.prioridad === 'Alta' && <span className="mt-1 block"><ReviewPriorityBadge priority={review.prioridad} urgent={review.estado === REVIEW_STATUS.NUEVA || review.estado === REVIEW_STATUS.EN_REVISION} /></span>}
          </span>
          <span className="flex max-w-full flex-wrap items-center gap-2">
            <ReviewRating value={review.puntuacion} />
            <ReviewStatusBadge status={review.estado} />
          </span>
        </span>

        <span className="mt-2 line-clamp-2 whitespace-pre-wrap break-words text-sm leading-5 text-slate-700">
          {review.contenido}
        </span>

        <span className="mt-3 grid min-w-0 grid-cols-2 gap-x-4 gap-y-2 border-t border-slate-100 pt-3 text-sm">
          <span className="min-w-0">
            <span className="block text-xs font-medium text-slate-500">Fecha</span>
            <span className="break-words text-slate-700"><ReviewDate value={review.fecha} /></span>
          </span>
          <span className="min-w-0">
            <span className="block text-xs font-medium text-slate-500">Fuente</span>
            <span className="break-all text-slate-700"><ReviewSource value={review.fuente} /></span>
          </span>
        </span>

        <span className="mt-3 block text-xs font-semibold text-sky-800">
          {isSelected ? 'Detalle seleccionado' : 'Abrir detalle'}
        </span>
      </button>
    </li>
  )
}


const PAGE_SIZE = 8

function ReviewTable({ reviews, selectedReviewId, onSelect }) {
  const [page, setPage] = useState(0)
  const lastPage = Math.max(0, Math.ceil(reviews.length / PAGE_SIZE) - 1)
  const currentPage = Math.min(page, lastPage)
  const start = currentPage * PAGE_SIZE
  const visibleReviews = reviews.slice(start, start + PAGE_SIZE)

  return (
    <>
      <ul aria-label="Reviews" className="grid min-w-0 gap-3 lg:hidden">
        {visibleReviews.map((review) => (
          <ReviewCard
            isSelected={review.id === selectedReviewId}
            key={review.id}
            onSelect={onSelect}
            review={review}
          />
        ))}
      </ul>
      <div className="hidden overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:block">
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
              {visibleReviews.map((review) => {
                const isSelected = review.id === selectedReviewId

                return (
                  <tr
                    aria-selected={isSelected}
                    className={`cursor-pointer transition ${isSelected ? 'bg-sky-50' : 'hover:bg-slate-50'}`}
                    data-review-id={review.id}
                    key={review.id}
                    onClick={(event) => onSelect(review.id, event.currentTarget)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        onSelect(review.id, event.currentTarget)
                      }
                    }}
                    tabIndex={0}
                  >
                    <td className="break-words px-5 py-4 font-medium text-slate-900">
                      {review.autor || 'Sin autor'}
                      {review.prioridad === 'Alta' && <div className="mt-1"><ReviewPriorityBadge priority={review.prioridad} urgent={review.estado === REVIEW_STATUS.NUEVA || review.estado === REVIEW_STATUS.EN_REVISION} /></div>}
                    </td>
                    <td className="px-5 py-4"><Summary content={review.contenido} /></td>
                    <td className="px-5 py-4 text-slate-600">
                      <ReviewDate value={review.fecha} />
                    </td>
                    <td className="break-words px-5 py-4 text-slate-600"><ReviewSource value={review.fuente} /></td>
                    <td className="whitespace-nowrap px-5 py-4"><ReviewRating value={review.puntuacion} /></td>
                    <td className="whitespace-nowrap px-5 py-4"><ReviewStatusBadge status={review.estado} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
      {lastPage > 0 && (
        <nav aria-label="Páginas de reseñas" className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <span aria-live="polite" className="text-sm tabular-nums text-slate-600">
            {start + 1}–{start + visibleReviews.length} de {reviews.length}
          </span>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="workspace-action min-h-11 aria-disabled:opacity-50" aria-disabled={currentPage === 0} onClick={() => { if (currentPage > 0) setPage(currentPage - 1) }}>Anterior</button>
            <button type="button" className="workspace-action min-h-11 aria-disabled:opacity-50" aria-disabled={currentPage === lastPage} onClick={() => { if (currentPage < lastPage) setPage(currentPage + 1) }}>Siguiente</button>
          </div>
        </nav>
      )}
    </>
  )
}

export default ReviewTable
