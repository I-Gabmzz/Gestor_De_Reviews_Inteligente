import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  ClipboardList,
  Inbox,
  MessageSquareText,
  RefreshCw,
  Star,
} from 'lucide-react'

import ReviewStatusBadge from '../components/reviews/ReviewStatusBadge.jsx'

import { formatDate } from '../utils/formatDate.js'
import { getDashboard } from '../services/dashboardService.js'
import { getStoredSession } from '../services/authService.js'
import './DashboardPage.css'

const EMPTY_DASHBOARD = {
  total_reviews: 0,
  promedio_puntuacion: null,
  reviews_nuevas: 0,
  reviews_en_revision: 0,
  reviews_atendidas: 0,
  reviews_urgentes: 0,
  reviews_recientes: [],
}


function formatAverage(value) {
  if (value === null || value === undefined) {
    return 'Sin datos'
  }

  return Number(value).toFixed(1)
}

function StatCard({ icon: Icon, label, value, helper, accentClassName, to }) {
  const MetricIcon = Icon

  return (
    <article className="dashboard-stat rounded-lg border border-[#e5e5ea] bg-white p-5 shadow-[0_14px_36px_rgba(0,0,0,0.07)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          {to ? (
            <Link className="dashboard-metric-link inline-flex min-h-11 min-w-11 items-center rounded text-sm font-medium text-slate-800 underline focus-visible:outline-2" to={to}>
              {label}
            </Link>
          ) : (
            <p className="text-sm font-medium text-slate-500">{label}</p>
          )}
          <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums text-[#1d1d1f]">{value}</p>
        </div>
        <span className={`dashboard-metric-icon grid size-11 shrink-0 place-items-center rounded-xl ${accentClassName}`}>
          <MetricIcon aria-hidden="true" size={20} strokeWidth={2.2} />
        </span>
      </div>
      <p className="mt-4 text-sm leading-5 text-slate-500">{helper}</p>
    </article>
  )
}

function StarScore({ value }) {
  if (value === null) {
    return <span className="text-sm text-slate-500">Sin puntuación</span>
  }

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
            className="h-36 motion-safe:animate-pulse rounded-lg border border-[#e5e5ea] bg-white p-5"
            key={item}
          >
            <div className="h-4 w-28 rounded bg-slate-200" />
            <div className="mt-5 h-8 w-20 rounded bg-slate-200" />
            <div className="mt-5 h-4 w-full rounded bg-slate-100" />
          </div>
        ))}
      </div>
      <div className="h-72 motion-safe:animate-pulse rounded-lg border border-[#e5e5ea] bg-white p-5">
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
      <section aria-label="Indicadores del negocio" className="dashboard-metrics grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          accentClassName="bg-slate-100 text-slate-900"
          helper="Reviews registradas para el negocio."
          icon={ClipboardList}
          label="Total de reviews"
          to="/reviews"
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
          to="/reviews?estado=nueva"
          value={dashboard.reviews_nuevas}
        />
        <StatCard
          accentClassName="bg-slate-100 text-slate-900"
          helper="Reviews pendientes de atención."
          icon={ClipboardList}
          label="Reviews en revisión"
          to="/reviews?estado=en_revision"
          value={dashboard.reviews_en_revision}
        />
        <StatCard
          accentClassName="bg-slate-100 text-slate-900"
          helper="Reviews con seguimiento completado."
          icon={ClipboardList}
          label="Reviews atendidas"
          to="/reviews?estado=atendida"
          value={dashboard.reviews_atendidas}
        />
        <StatCard
          accentClassName="bg-slate-100 text-slate-900"
          helper="Reviews pendientes de prioridad alta."
          icon={AlertCircle}
          label="Reviews urgentes"
          to="/reviews?urgente=true"
          value={dashboard.reviews_urgentes}
        />
      </section>

      <section className="dashboard-recent rounded-lg border border-[#e5e5ea] bg-white p-5 shadow-[0_14px_36px_rgba(0,0,0,0.07)] sm:p-6">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
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
    <main className="dashboard-motion dashboard-workspace min-h-screen text-slate-900">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-8">
        <header className="dashboard-workspace-header flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            {dashboard.nombre_negocio && <p className="mb-1 text-sm font-medium text-slate-600">Resumen del negocio</p>}
            <h1 className="workspace-title wrap-anywhere">{dashboard.nombre_negocio || 'Resumen'}</h1>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            {getStoredSession()?.user?.rol === 'admin_tenant' && <Link className="workspace-action min-h-11" to="/users">Usuarios</Link>}
            <Link className="workspace-action min-h-11" to="/imports">Importar reviews</Link>
            <Link className="workspace-action dashboard-primary min-h-11" to="/reviews">Ver todas</Link>
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
