import { useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  ClipboardList,
  Inbox,
  MessageSquareText,
  RefreshCw,
  Star,
  Table2,
  Upload,
  UsersRound,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import ReviewStatusBadge from '../components/reviews/ReviewStatusBadge.jsx'

import { formatDate } from '../utils/formatDate.js'
import { getDashboard } from '../services/dashboardService.js'
import { getStoredSession } from '../services/authService.js'

const EMPTY_DASHBOARD = {
  total_reviews: 0,
  promedio_puntuacion: null,
  reviews_nuevas: 0,
  reviews_recientes: [],
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
    <article className="dashboard-stat rounded-lg border border-[#e5e5ea] bg-white p-5 shadow-[0_14px_36px_rgba(0,0,0,0.07)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-[#1d1d1f]">{value}</p>
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
    <span className="inline-flex items-center gap-1 text-sm font-semibold text-[#1d1d1f]">
      <Star aria-hidden="true" className="fill-amber-400 text-amber-400" size={16} />
      {score}/5
    </span>
  )
}


function LoadingSkeleton() {
  return (
    <div aria-label="Cargando dashboard" className="space-y-6" role="status">
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((item) => (
          <div
            className="h-36 animate-pulse rounded-lg border border-[#e5e5ea] bg-white p-5"
            key={item}
          >
            <div className="h-4 w-28 rounded bg-slate-200" />
            <div className="mt-5 h-8 w-20 rounded bg-slate-200" />
            <div className="mt-5 h-4 w-full rounded bg-slate-100" />
          </div>
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-lg border border-[#e5e5ea] bg-white p-5">
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
    <div className="rounded-lg border border-dashed border-[#d2d2d7] bg-[#fafafa] px-5 py-10 text-center">
      <Inbox aria-hidden="true" className="mx-auto text-slate-400" size={32} />
      <h3 className="mt-3 text-base font-semibold text-[#1d1d1f]">Todavía no existen reviews</h3>
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
    <div className="overflow-hidden rounded-lg border border-[#e5e5ea]">
      <div className="overflow-x-auto">
        <table className="ui-table min-w-[46rem] w-full border-collapse bg-white text-left text-sm">
          <thead className="bg-[#f5f5f7] text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-semibold" scope="col">Autor</th>
              <th className="px-4 py-3 font-semibold" scope="col">Puntuación</th>
              <th className="px-4 py-3 font-semibold" scope="col">Review</th>
              <th className="px-4 py-3 font-semibold" scope="col">Fecha</th>
              <th className="px-4 py-3 font-semibold" scope="col">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ededf0]">
            {reviews.map((review) => (
              <tr className="align-top" key={review.id}>
                <td className="px-4 py-4 font-medium text-[#1d1d1f]">{review.autor || 'Sin autor'}</td>
                <td className="px-4 py-4">
                  <StarScore value={review.puntuacion} />
                </td>
                <td className="max-w-md px-4 py-4 leading-6 text-slate-600">
                  <p className="line-clamp-2">{review.contenido}</p>
                </td>
                <td className="px-4 py-4 text-slate-600">{formatDate(review.fecha)}</td>
                <td className="px-4 py-4">
                  <ReviewStatusBadge status={review.estado} />
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
          accentClassName="bg-slate-100 text-slate-900"
          helper="Reviews registradas para el negocio."
          icon={ClipboardList}
          label="Total de reviews"
          value={dashboard.total_reviews}
        />
        <StatCard
          accentClassName="bg-slate-100 text-slate-900"
          helper="Promedio general de puntuación."
          icon={Star}
          label="Promedio de puntuación"
          value={formatAverage(dashboard.promedio_puntuacion)}
        />
        <StatCard
          accentClassName="bg-slate-100 text-slate-900"
          helper='Reviews con estado "nueva".'
          icon={MessageSquareText}
          label="Reviews nuevas"
          value={dashboard.reviews_nuevas}
        />
      </section>

      <section className="dashboard-recent rounded-lg border border-[#e5e5ea] bg-white p-5 shadow-[0_14px_36px_rgba(0,0,0,0.07)] sm:p-6">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-[#515154]">Seguimiento</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1d1d1f]">Reviews recientes</h2>
          </div>
          <p className="text-sm text-slate-500">Últimas 5 reviews registradas</p>
        </div>

        {isEmpty && (
          <p className="mb-4 rounded-lg border border-[#e5e5ea] bg-[#f5f5f7] px-4 py-3 text-sm text-slate-600">
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
  const canManageUsers = getStoredSession()?.user?.rol === 'admin_tenant'
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
    <main className="dashboard-motion min-h-screen bg-[#f5f5f7] px-5 py-6 text-[#1d1d1f] sm:px-8 lg:px-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 rounded-lg border border-[#e5e5ea] bg-white px-5 py-5 shadow-[0_14px_36px_rgba(0,0,0,0.07)] lg:flex-row lg:items-center lg:justify-between sm:px-6">
          <div>
            <p className="text-sm font-medium text-[#515154]">Gestor Inteligente de Reviews</p>
            <h1 className="mt-1 break-words text-3xl font-bold tracking-tight text-[#1d1d1f] sm:text-4xl">{dashboard.nombre_negocio || 'Dashboard'}</h1>
            {dashboard.nombre_negocio && <p className="mt-1 text-sm font-medium text-[#515154]">Dashboard del negocio</p>}
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Vista general de las reseñas del negocio y su estado actual de seguimiento.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            {canManageUsers && (
              <Link
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm font-semibold text-[#1d1d1f] transition hover:bg-[#f5f5f7] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
                to="/users"
              >
                <UsersRound aria-hidden="true" size={16} />
                Usuarios
              </Link>
            )}
            <Link
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#1d1d1f] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#333336] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200"
              to="/imports"
            >
              <Upload aria-hidden="true" size={16} />
              Importar reviews
            </Link>
            <Link
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm font-semibold text-[#1d1d1f] transition hover:bg-[#f5f5f7] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
              to="/reviews"
            >
              <Table2 aria-hidden="true" size={16} />
              Ver todas
            </Link>
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
