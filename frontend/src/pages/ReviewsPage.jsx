import { useEffect, useState } from 'react'
import { AlertCircle, Inbox, MessageSquareText, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'

import { getReviewById, getReviews } from '../api/reviews.js'
import ReviewDetail from '../components/reviews/ReviewDetail.jsx'
import ReviewTable from '../components/reviews/ReviewTable.jsx'


function getErrorMessage(error) {
  if (error.response?.status === 401) {
    return 'Tu sesión no es válida. Inicia sesión nuevamente.'
  }
  if (error.response?.status === 403) {
    return 'Tu usuario no tiene un tenant asignado.'
  }
  return 'No fue posible cargar las reviews. Intenta nuevamente.'
}

function ReviewsPage() {
  const [reviews, setReviews] = useState([])
  const [selectedReviewId, setSelectedReviewId] = useState(null)
  const [selectedReview, setSelectedReview] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function loadReviews() {
      setIsLoading(true)
      setErrorMessage('')

      try {
        const data = await getReviews({ signal: controller.signal })
        setReviews(data.items)
        setSelectedReviewId((currentId) => currentId ?? data.items[0]?.id ?? null)
      } catch (error) {
        if (error.code !== 'ERR_CANCELED') {
          setErrorMessage(getErrorMessage(error))
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      }
    }

    loadReviews()
    return () => controller.abort()
  }, [reloadKey])

  useEffect(() => {
    if (selectedReviewId === null) {
      setSelectedReview(null)
      return undefined
    }

    const controller = new AbortController()

    async function loadReviewDetail() {
      setIsDetailLoading(true)
      try {
        const data = await getReviewById(selectedReviewId, { signal: controller.signal })
        setSelectedReview(data)
      } catch (error) {
        if (error.code !== 'ERR_CANCELED') {
          setSelectedReview(null)
          setErrorMessage(getErrorMessage(error))
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsDetailLoading(false)
        }
      }
    }

    loadReviewDetail()
    return () => controller.abort()
  }, [selectedReviewId])

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
          <Link className="flex items-center gap-3 font-semibold text-slate-900" to="/dashboard">
            <span className="grid size-9 place-items-center rounded-lg bg-sky-600 text-white">
              <MessageSquareText aria-hidden="true" size={20} />
            </span>
            Gestor de Reviews
          </Link>
          <span className="text-sm text-slate-500">Consulta de reviews</span>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-sky-700">HU-07</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Reviews de clientes</h1>
            <p className="mt-2 text-sm text-slate-600">
              Consulta los comentarios registrados para tu organización.
            </p>
          </div>
          <button
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isLoading}
            onClick={() => setReloadKey((value) => value + 1)}
            type="button"
          >
            <RefreshCw aria-hidden="true" className={isLoading ? 'animate-spin' : ''} size={16} />
            Actualizar
          </button>
        </div>

        {errorMessage && (
          <div className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
            {errorMessage}
          </div>
        )}

        {isLoading && (
          <div className="mt-6 rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500" aria-live="polite">
            Cargando reviews…
          </div>
        )}

        {!isLoading && !errorMessage && reviews.length === 0 && (
          <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
            <Inbox aria-hidden="true" className="mx-auto text-slate-400" size={34} />
            <h2 className="mt-3 font-semibold text-slate-800">Todavía no hay reviews</h2>
            <p className="mt-1 text-sm text-slate-500">Las reviews importadas aparecerán en esta sección.</p>
          </div>
        )}

        {!isLoading && reviews.length > 0 && (
          <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section aria-label="Listado de reviews">
              <div className="mb-3 text-sm text-slate-500">
                {reviews.length} {reviews.length === 1 ? 'review encontrada' : 'reviews encontradas'}
              </div>
              <ReviewTable
                onSelect={setSelectedReviewId}
                reviews={reviews}
                selectedReviewId={selectedReviewId}
              />
            </section>
            <ReviewDetail isLoading={isDetailLoading} review={selectedReview} />
          </div>
        )}
      </div>
    </main>
  )
}

export default ReviewsPage
