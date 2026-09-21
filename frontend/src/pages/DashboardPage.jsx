import { useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  ClipboardList,
  Inbox,
  MessageSquareText,
  RefreshCw,
  Star,
} from 'lucide-react'

import { formatDate } from '../utils/formatDate.js'
import { getDashboard } from '../services/dashboardService.js'

const EMPTY_DASHBOARD = {
  total_reviews: 0,
  promedio_puntuacion: null,
  reviews_nuevas: 0,
  reviews_recientes: [],
}

const statusStyles = {
  Nueva: 'border-teal-200 bg-teal-50 text-teal-700',
  'En revisión': 'border-amber-200 bg-amber-50 text-amber-700',
  Atendida: 'border-emerald-200 bg-emerald-50 text-emerald-700',
}

function formatAverage(value) {
  if (value === null || value === undefined) {
    return 'Sin datos'
  }

  return Number(value).toFixed(1)
}

function StatCard({ icon: Icon, label, value, helper, accentClassName }) {
  const MetricIcon = Icon

  return (
    <article className="rounded-lg border border-[#d8e1ec] bg-white p-5 shadow-[0_14px_36px_rgba(16,35,63,0.07)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-[#10233f]">{value}</p>
        </div>
        <span className={`grid size-10 shrink-0 place-items-center rounded-lg ${accentClassName}`}>
          <MetricIcon aria-hidden="true" size={20} strokeWidth={2.2} />
        </span>
      </div>
      <p className="mt-4 text-sm leading-5 text-slate-500">{helper}</p>
    </article>
  )
}

function StarScore({ value }) {
  const score = Number(value) || 0

  return (
    <span className="inline-flex items-center gap-1 text-sm font-semibold text-[#10233f]">
      <Star aria-hidden="true" className="fill-amber-400 text-amber-400" size={16} />
      {score}/5
    </span>
  )
}

function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${
        statusStyles[status] ?? 'border-slate-200 bg-slate-50 text-slate-600'
      }`}
    >
      {status}
    </span>
  )
}

function LoadingSkeleton() {
  return (
    <div aria-label="Cargando dashboard" className="space-y-6" role="status">
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((item) => (
          <div
            className="h-36 animate-pulse rounded-lg border border-[#d8e1ec] bg-white p-5"
            key={item}
          >
            <div className="h-4 w-28 rounded bg-slate-200" />
            <div className="mt-5 h-8 w-20 rounded bg-slate-200" />
            <div className="mt-5 h-4 w-full rounded bg-slate-100" />
          </div>
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-lg border border-[#d8e1ec] bg-white p-5">
        <div className="h-5 w-40 rounded bg-slate-200" />
        <div className="mt-6 space-y-3">
          {[0, 1, 2, 3].map((item) => (
            <div className="h-10 rounded bg-slate-100" key={item} />
          ))}
        </div>
      </div>
    </div>
  )
}

function ErrorState({ message, onRetry }) {
  return (
    <section className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-800" role="alert">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
          <div>
            <h2 className="text-base font-semibold">No se pudo cargar el dashboard</h2>
            <p className="mt-1 text-sm leading-6 text-red-700">
              {message || 'Intenta nuevamente para consultar el estado de tus reviews.'}
            </p>
          </div>
        </div>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-800 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-red-200"
          onClick={onRetry}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={16} />
          Reintentar
        </button>
      </div>
    </section>
  )
}

function EmptyReviewsState() {
  return (
    <div className="rounded-lg border border-dashed border-[#cbd6e3] bg-[#fbfcfe] px-5 py-10 text-center">
      <Inbox aria-hidden="true" className="mx-auto text-slate-400" size={32} />
      <h3 className="mt-3 text-base font-semibold text-[#10233f]">Todavía no existen reviews</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
        Cuando se importen reseñas para este negocio, las más recientes aparecerán en esta sección.
      </p>
    </div>
  )
}

function RecentReviewsTable({ reviews }) {
  if (reviews.length === 0) {
    return <EmptyReviewsState />
  }

  return (
    <div className="overflow-hidden rounded-lg border border-[#d8e1ec]">
      <div className="overflow-x-auto">
        <table className="min-w-[46rem] w-full border-collapse bg-white text-left text-sm">
          <thead className="bg-[#f6f8fb] text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-semibold">Autor</th>
              <th className="px-4 py-3 font-semibold">Puntuación</th>
              <th className="px-4 py-3 font-semibold">Review</th>
              <th className="px-4 py-3 font-semibold">Fecha</th>
              <th className="px-4 py-3 font-semibold">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e6edf5]">
            {reviews.map((review) => (
              <tr className="align-top" key={review.id}>
                <td className="px-4 py-4 font-medium text-[#10233f]">{review.autor || 'Sin autor'}</td>
                <td className="px-4 py-4">
                  <StarScore value={review.puntuacion} />
                </td>
                <td className="max-w-md px-4 py-4 leading-6 text-slate-600">
                  <p className="line-clamp-2">{review.contenido}</p>
                </td>
                <td className="px-4 py-4 text-slate-600">{formatDate(review.fecha)}</td>
                <td className="px-4 py-4">
                  <StatusBadge status={review.estado} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DashboardContent({ dashboard }) {
  const isEmpty = dashboard.total_reviews === 0

  return (
    <>
      <section className="grid gap-4 md:grid-cols-3">
        <StatCard
          accentClassName="bg-[#10233f] text-teal-200"
          helper="Reviews registradas para el negocio."
          icon={ClipboardList}
          label="Total de reviews"
          value={dashboard.total_reviews}
        />
        <StatCard
          accentClassName="bg-amber-100 text-amber-700"
          helper="Promedio general de puntuación."
          icon={Star}
          label="Promedio de puntuación"
          value={formatAverage(dashboard.promedio_puntuacion)}
        />
        <StatCard
          accentClassName="bg-teal-100 text-teal-700"
          helper='Reviews con estado "Nueva".'
          icon={MessageSquareText}
          label="Reviews nuevas"
          value={dashboard.reviews_nuevas}
        />
      </section>

      <section className="rounded-lg border border-[#d8e1ec] bg-white p-5 shadow-[0_14px_36px_rgba(16,35,63,0.07)] sm:p-6">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-[#0f766e]">Seguimiento</p>
            <h2 className="mt-1 text-xl font-semibold text-[#10233f]">Reviews recientes</h2>
          </div>
          <p className="text-sm text-slate-500">Últimas 5 reviews registradas</p>
        </div>

        {isEmpty && (
          <p className="mb-4 rounded-lg border border-[#d8e1ec] bg-[#f6f8fb] px-4 py-3 text-sm text-slate-600">
            Aún no hay datos para calcular métricas del negocio.
          </p>
        )}

        <RecentReviewsTable reviews={dashboard.reviews_recientes} />
      </section>
    </>
  )
}

function getDashboardErrorMessage(error) {
  if (!error.response) {
    return 'No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.'
  }

  if (error.response.status === 401) {
    return 'Tu sesión no está disponible o expiró. Inicia sesión nuevamente para consultar el dashboard.'
  }

  if (error.response.status === 403) {
    return 'Tu usuario no tiene acceso a un dashboard de negocio.'
  }

  return 'No pudimos cargar las métricas del dashboard. Inténtalo nuevamente.'
}

function DashboardPage() {
  const [dashboard, setDashboard] = useState(EMPTY_DASHBOARD)
  const [status, setStatus] = useState('loading')
  const [errorMessage, setErrorMessage] = useState('')

  const loadDashboard = useCallback(async () => {
    setStatus('loading')
    setErrorMessage('')

    try {
      const dashboardData = await getDashboard()
      setDashboard(dashboardData)
      setStatus('ready')
    } catch (error) {
      setDashboard(EMPTY_DASHBOARD)
      setErrorMessage(getDashboardErrorMessage(error))
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  return (
    <main className="min-h-screen bg-[#eef2f7] px-5 py-6 text-[#10233f] sm:px-8 lg:px-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 rounded-lg border border-[#d8e1ec] bg-white px-5 py-5 shadow-[0_14px_36px_rgba(16,35,63,0.07)] sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-sm font-medium text-[#0f766e]">Gestor Inteligente de Reviews</p>
            <h1 className="mt-1 text-2xl font-semibold text-[#10233f] sm:text-3xl">Dashboard</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Vista general de las reseñas del negocio y su estado actual de seguimiento.
            </p>
          </div>
        </header>

        {status === 'loading' && <LoadingSkeleton />}
        {status === 'error' && <ErrorState message={errorMessage} onRetry={loadDashboard} />}
        {status !== 'loading' && status !== 'error' && <DashboardContent dashboard={dashboard} />}
      </div>
    </main>
  )
}

export default DashboardPage
