import { useEffect, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, Download, Inbox, MessageSquarePlus, RefreshCw, RotateCcw, Search, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { exportReviews, getReviewById, getReviews, updateReviewStatus } from '../services/reviewService.js'
import ReviewDetail from '../components/reviews/ReviewDetail.jsx'
import ReviewEditForm from '../components/reviews/ReviewEditForm.jsx'
import ReviewTable from '../components/reviews/ReviewTable.jsx'
import { REVIEW_STATUS_OPTIONS } from '../utils/reviewStatus.js'
import { getStoredSession } from '../services/authService.js'
import { getDashboard } from '../services/dashboardService.js'
import { canClassifyReview, mergeClassification } from '../utils/reviewClassification.js'
import { canAccessRoute } from '../utils/roleAccess.js'
import { mergeSuggestedResponse } from '../utils/reviewSuggestedResponse.js'
import { canPrioritizeReview, mergePriority } from '../utils/reviewPriority.js'


const emptyFilters = {
  fecha_desde: '',
  fecha_hasta: '',
  puntuacion: '',
  estado: '',
  fuente: '',
}

const filterControlClassName = 'w-full min-w-0'


function getErrorMessage(error) {
  if (error.response?.status === 401) {
    return 'Tu sesión no es válida. Inicia sesión nuevamente.'
  }
  if (error.response?.status === 403) {
    return 'No tienes permiso para consultar las reviews. Si tu acceso cambió, vuelve a iniciar sesión.'
  }
  if (error.response?.status === 422) {
    return 'Revisa las fechas y los filtros seleccionados e inténtalo nuevamente.'
  }
  return 'No fue posible cargar las reviews. Intenta nuevamente.'
}

function getStatusErrorMessage(error) {
  if (!error.response) {
    return 'No pudimos confirmar el cambio. Se muestra el último estado confirmado. Intenta nuevamente.'
  }
  if (error.response?.status === 401) {
    return 'Tu sesión expiró. Inicia sesión nuevamente para cambiar el estado.'
  }
  if (error.response?.status === 403) {
    return 'Tu usuario no tiene permiso para cambiar el estado de esta review.'
  }
  if (error.response?.status === 404) {
    return 'La review ya no está disponible. Actualiza la lista e inténtalo de nuevo.'
  }
  if (error.response?.status === 422) {
    return 'El estado elegido no es válido. Selecciona Nueva, En revisión o Atendida.'
  }
  return 'No fue posible guardar el estado. Se muestra el último estado confirmado. Intenta nuevamente.'
}

function getDetailErrorMessage(error) {
  const status = error.response?.status
  if (status === 401 || status === 403) return getErrorMessage(error)
  if (status === 404) return 'Esta reseña ya no está disponible.'
  return 'No pudimos cargar el detalle de la reseña.'
}


function getExportErrorMessage(error) {
  if (error.code === 'INVALID_CSV_RESPONSE') return 'El servidor no devolvió un CSV válido. Inténtalo nuevamente.'
  if (error.response?.status === 401) return 'Tu sesión expiró. Inicia sesión nuevamente para exportar.'
  if (error.response?.status === 403) return 'No tienes permiso para exportar las reviews.'
  if (error.response?.status === 422) return 'Revisa los filtros antes de exportar.'
  if (!error.response) return 'No pudimos conectar con el servidor para exportar. Inténtalo nuevamente.'
  return 'No fue posible exportar las reviews. Inténtalo nuevamente.'
}


function exportFilename(contentDisposition) {
  const fallback = `reviews_${new Date().toISOString().slice(0, 10).replaceAll('-', '')}.csv`
  const filename = /(?:^|;)\s*filename\s*=\s*(?:"([^"]+)"|([^;]+))/i.exec(contentDisposition || '')
  const candidate = filename?.[1] ?? filename?.[2]?.trim()
  return candidate && /^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}\.csv$/i.test(candidate) && !candidate.includes('..')
    ? candidate
    : fallback
}


function downloadCsv(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  try {
    link.href = url
    link.download = filename
    link.hidden = true
    document.body.append(link)
    link.click()
  } finally {
    link.remove()
    URL.revokeObjectURL(url)
  }
}

function ReviewsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedValue = searchParams.get('review')
  const requestedReviewId = /^[1-9]\d*$/.test(requestedValue || '') && Number.isSafeInteger(Number(requestedValue)) ? Number(requestedValue) : null
  const detailAnchor = useRef(null)
  const [reviews, setReviews] = useState([])
  const [searchText, setSearchText] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [filters, setFilters] = useState(emptyFilters)
  const [debouncedSource, setDebouncedSource] = useState('')
  const [selectedReviewId, setSelectedReviewId] = useState(requestedReviewId)
  const [selectedReview, setSelectedReview] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [detailError, setDetailError] = useState(null)
  const [statusFeedback, setStatusFeedback] = useState(null)
  const [isStatusSaving, setIsStatusSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [listReloadKey, setListReloadKey] = useState(0)
  const [detailReloadKey, setDetailReloadKey] = useState(0)
  const [editingReview, setEditingReview] = useState(null)
  const [successMessage, setSuccessMessage] = useState('')
  const [listedCriteria, setListedCriteria] = useState(null)
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const [business, setBusiness] = useState(null)
  const exportPending = useRef(false)
  const statusSavePending = useRef(false)
  const retainedDetail = useRef(null)
  const { fecha_desde, fecha_hasta, puntuacion, estado } = filters
  const hasActiveFilters = Object.values(filters).some(Boolean)
  const hasActiveCriteria = Boolean(debouncedSearch.trim()) || Object.values(filters).some((value) => Boolean(value.trim()))
  const session = getStoredSession()
  const tenantId = session?.user?.tenant_id
  const canClassify = canClassifyReview(session)
  const canPrioritize = canPrioritizeReview(session)
  const canExport = canAccessRoute(session?.user?.rol, '/reviews')
  const selectedDetail = selectedReview?.id === selectedReviewId ? selectedReview : null
  const selectedDetailError = detailError?.reviewId === selectedReviewId ? detailError.message : ''
  const showDetail = selectedReviewId !== null || (!isLoading && !errorMessage && reviews.length > 0)

  useEffect(() => {
    if (tenantId == null || !canExport) return
    const controller = new AbortController()
    getDashboard({ signal: controller.signal }).then(
      (dashboard) => {
        if (!controller.signal.aborted) setBusiness({ tenantId, name: dashboard?.nombre_negocio })
      },
      () => { /* El nombre es complementario a la consulta de reseñas. */ },
    )
    return () => controller.abort()
  }, [canExport, tenantId])

  function handleSuggested(result) {
    setSelectedReview((current) => mergeSuggestedResponse(current, result))
    setReviews((current) => current.map((review) => mergeSuggestedResponse(review, result)))
  }

  function handlePrioritized(result) {
    setSelectedReview((current) => mergePriority(current, result))
    setReviews((current) => current.map((review) => mergePriority(review, result)))
    window.dispatchEvent(new window.Event('review-priority-saved'))
  }

  useEffect(() => {
    if (requestedReviewId === null) return
    setSelectedReviewId(requestedReviewId)
    setFilters(emptyFilters)
    setSearchText('')
    setDebouncedSearch('')
    setDebouncedSource('')
    setStatusFeedback(null)
    setErrorMessage('')
  }, [requestedReviewId])

  useEffect(() => {
    if (requestedReviewId === null || isDetailLoading || (selectedReview?.id !== requestedReviewId && !selectedDetailError)) return
    detailAnchor.current?.scrollIntoView?.({ block: 'start', behavior: 'auto' })
    detailAnchor.current?.focus({ preventScroll: true })
  }, [requestedReviewId, selectedReview?.id, selectedDetailError, isDetailLoading])

  function handleClassified(result) {
    setSelectedReview((current) => mergeClassification(current, result))
    setReviews((current) => current.map((review) => mergeClassification(review, result)))
  }
  const canDetectTopic = canAccessRoute(session?.user?.rol, '/reviews')

  function handleTopicDetected(result) {
    const mergeTopic = (current) => (
      current?.id === result.id && current.tenant_id === result.tenant_id && current.contenido === result.contenido
        ? { ...current, tema: result.tema }
        : current
    )
    setSelectedReview(mergeTopic)
    setReviews((current) => current.map(mergeTopic))
  }

  function handleFilterChange(event) {
    const { name, value } = event.target
    setFilters((current) => ({ ...current, [name]: value }))
  }

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSearch(searchText), 400)
    return () => clearTimeout(timeout)
  }, [searchText])

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSource(filters.fuente), 400)
    return () => clearTimeout(timeout)
  }, [filters.fuente])

  useEffect(() => {
    const controller = new AbortController()

    async function loadReviews() {
      setIsLoading(true)
      setErrorMessage('')

      try {
        const criteria = {
          busqueda: debouncedSearch,
          fecha_desde,
          fecha_hasta,
          puntuacion,
          estado,
          fuente: debouncedSource,
        }
        const data = await getReviews(criteria, { signal: controller.signal })
        if (controller.signal.aborted) return
        const criteriaKey = JSON.stringify(criteria)
        const keepDetail = (id) => id === requestedReviewId
          || (retainedDetail.current?.id === id && retainedDetail.current.criteriaKey === criteriaKey)
        setListedCriteria(criteria)
        setReviews(data.items)
        setSelectedReviewId((currentId) => {
          if (requestedReviewId !== null) return requestedReviewId
          if (currentId === null) return data.items[0]?.id ?? null
          return keepDetail(currentId) || data.items.some((review) => review.id === currentId) ? currentId : null
        })
        setSelectedReview((current) => {
          if (current === null) return null
          if (keepDetail(current.id)) return current
          return data.items.find((review) => review.id === current.id) ?? null
        })
      } catch (error) {
        if (!controller.signal.aborted && error.code !== 'ERR_CANCELED') {
          setErrorMessage(getErrorMessage(error))
          if (error.response?.status === 401 || error.response?.status === 403) {
            retainedDetail.current = null
            setSelectedReviewId(null)
            setSelectedReview(null)
            setStatusFeedback(null)
          }
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      }
    }

    loadReviews()
    return () => controller.abort()
  }, [debouncedSearch, debouncedSource, fecha_desde, fecha_hasta, puntuacion, estado, reloadKey, listReloadKey, requestedReviewId])

  useEffect(() => {
    if (selectedReviewId === null) {
      setSelectedReview(null)
      setIsDetailLoading(false)
      return undefined
    }

    const controller = new AbortController()

    async function loadReviewDetail() {
      setIsDetailLoading(true)
      setDetailError(null)
      try {
        const data = await getReviewById(selectedReviewId, { signal: controller.signal })
        if (controller.signal.aborted) return
        setSelectedReview(data)
      } catch (error) {
        if (!controller.signal.aborted && error.code !== 'ERR_CANCELED') {
          setSelectedReview(null)
          setDetailError({ reviewId: selectedReviewId, message: getDetailErrorMessage(error) })
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsDetailLoading(false)
        }
      }
    }

    loadReviewDetail()
    return () => controller.abort()
  }, [selectedReviewId, reloadKey, detailReloadKey])

  function handleEdit(review) {
    setSuccessMessage('')
    setEditingReview(review)
  }

  function handleSummarySaved(updatedReview) {
    // Guardar solo el resumen evita pisar cambios de estado/edición concurrentes.
    function applySummary(current) {
      return current?.id === updatedReview.id && current.tenant_id === updatedReview.tenant_id && current.contenido === updatedReview.contenido
        ? { ...current, resumen: updatedReview.resumen }
        : current
    }
    setSelectedReview(applySummary)
    setReviews((current) => current.map(applySummary))
  }

  function handleSolutionSaved(updatedReview) {
    const applySolution = (current) => (
      current?.id === updatedReview.id && current.tenant_id === updatedReview.tenant_id && current.contenido === updatedReview.contenido
        ? { ...current, solucion: updatedReview.solucion }
        : current
    )
    setSelectedReview(applySolution)
    setReviews((current) => current.map(applySolution))
  }

  function handleSaved(updatedReview) {
    setSelectedReview(updatedReview)
    setReloadKey((value) => value + 1)
    setEditingReview(null)
    setErrorMessage('')
    setStatusFeedback(null)
    setSuccessMessage('Los cambios de la review se guardaron correctamente.')
  }

  async function handleStatusConfirm(estado) {
    if (!selectedDetail || statusSavePending.current) {
      return false
    }

    const { id: reviewId, tenant_id: reviewTenantId } = selectedDetail
    statusSavePending.current = true
    setIsStatusSaving(true)
    setStatusFeedback(null)
    setSuccessMessage('')

    try {
      const updatedReview = await updateReviewStatus(reviewId, estado)
      if (updatedReview?.id !== reviewId || updatedReview.tenant_id !== reviewTenantId || updatedReview.estado !== estado) {
        setStatusFeedback({ reviewId, kind: 'error', message: 'El servidor no confirmó el cambio. Actualiza la reseña o reintenta el guardado.' })
        return false
      }
      retainedDetail.current = { id: reviewId, criteriaKey: JSON.stringify(listedCriteria) }
      setSelectedReview((current) => (
        current?.id === reviewId && current.tenant_id === reviewTenantId ? { ...current, estado: updatedReview.estado } : current
      ))
      setStatusFeedback({ reviewId, kind: 'success', message: 'Estado guardado.' })
      setListReloadKey((value) => value + 1)
      return true
    } catch (error) {
      setStatusFeedback({ reviewId, kind: 'error', message: getStatusErrorMessage(error) })
      return false
    } finally {
      statusSavePending.current = false
      setIsStatusSaving(false)
    }
  }

  function handleSelectReview(reviewId) {
    if (requestedReviewId !== null) setSearchParams((current) => { current.delete('review'); return current }, { replace: true })
    if (reviewId !== selectedReviewId) {
      retainedDetail.current = null
      setStatusFeedback(null)
    }
    setSelectedReviewId(reviewId)
  }

  async function handleExport() {
    if (exportPending.current || !listedCriteria || isLoading || errorMessage) return
    exportPending.current = true
    setIsExporting(true)
    setExportError('')
    try {
      const { blob, contentDisposition } = await exportReviews(listedCriteria)
      downloadCsv(blob, exportFilename(contentDisposition))
    } catch (error) {
      setExportError(getExportErrorMessage(error))
    } finally {
      exportPending.current = false
      setIsExporting(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between lg:pt-2">
          <div className="min-w-0">
            <h1 className="workspace-title">Reseñas</h1>
            {business?.name && business.tenantId === tenantId && (
              <p className="mt-2 wrap-anywhere text-sm text-slate-600">{business.name}</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              className="workspace-action workspace-action-primary"
              to="/reviews/new"
            >
              <MessageSquarePlus aria-hidden="true" size={16} />
              Registrar reseña
            </Link>
            <button
              className="workspace-action"
              disabled={isLoading}
              onClick={() => setReloadKey((value) => value + 1)}
              type="button"
            >
              <RefreshCw aria-hidden="true" className={isLoading ? 'motion-safe:animate-spin' : ''} size={16} />
              Actualizar
            </button>
          </div>
        </header>

        <section aria-label="Búsqueda y filtros de reseñas" className="mt-6 flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
          <div className="w-full min-w-0 sm:max-w-md">
            <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-search">
              Buscar por contenido
            </label>
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                className="w-full"
                id="review-search"
                inputMode="search"
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="Buscar por contenido..."
                type="text"
                value={searchText}
              />
              {searchText && (
                <button
                  aria-label="Limpiar búsqueda"
                  className="absolute right-1 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600"
                  onClick={() => setSearchText('')}
                  title="Limpiar búsqueda"
                  type="button"
                >
                  <X aria-hidden="true" size={18} />
                </button>
              )}
            </div>
          </div>
          <div className="w-full border-t border-slate-200 pt-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-800">Filtros</h2>
                {hasActiveFilters && <span className="text-xs font-medium text-sky-700">Filtros activos</span>}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  className="workspace-action"
                  disabled={!hasActiveFilters}
                  onClick={() => {
                    setFilters(emptyFilters)
                    setDebouncedSource('')
                  }}
                  type="button"
                >
                  <RotateCcw aria-hidden="true" size={16} />
                  Limpiar filtros
                </button>
                {canExport && (
                  <button
                    aria-busy={isExporting}
                    className="workspace-action"
                    disabled={isExporting || isLoading || !listedCriteria || Boolean(errorMessage)}
                    onClick={handleExport}
                    type="button"
                  >
                    <Download aria-hidden="true" size={16} />
                    {isExporting ? 'Exportando CSV…' : 'Exportar CSV'}
                  </button>
                )}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-fecha-desde">Desde</label>
                <input className={filterControlClassName} id="review-fecha-desde" name="fecha_desde" onChange={handleFilterChange} type="date" value={filters.fecha_desde} />
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-fecha-hasta">Hasta</label>
                <input className={filterControlClassName} id="review-fecha-hasta" name="fecha_hasta" onChange={handleFilterChange} type="date" value={filters.fecha_hasta} />
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-puntuacion">Puntuación</label>
                <select className={filterControlClassName} id="review-puntuacion" name="puntuacion" onChange={handleFilterChange} value={filters.puntuacion}>
                  <option value="">Todas</option>
                  {[1, 2, 3, 4, 5].map((score) => <option key={score} value={score}>{score}</option>)}
                </select>
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-estado">Estado</label>
                <select className={filterControlClassName} id="review-estado" name="estado" onChange={handleFilterChange} value={filters.estado}>
                  <option value="">Todos los estados</option>
                  {REVIEW_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-fuente">Fuente</label>
                <input className={filterControlClassName} id="review-fuente" name="fuente" onChange={handleFilterChange} placeholder="Cualquier fuente" type="text" value={filters.fuente} />
              </div>
            </div>
          </div>
        </section>

        {exportError && (
          <div className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
            {exportError}
          </div>
        )}

        {errorMessage && (
          <div className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
            {errorMessage}
          </div>
        )}

        {successMessage && (
          <div className="mt-6 flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800" role="status">
            <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
            {successMessage}
          </div>
        )}

        <div className={`mt-6 grid items-start gap-6 ${showDetail ? 'xl:grid-cols-[minmax(0,1fr)_440px]' : ''}`}>
          <section aria-label="Listado de reviews" className="min-w-0" aria-busy={isLoading}>
            {isLoading && (
              <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500" role="status">
                Cargando reviews…
              </p>
            )}
            {!isLoading && !errorMessage && (
              reviews.length > 0 ? (
                <>
                  <p className="mb-3 text-sm text-slate-500">
                    {reviews.length} {reviews.length === 1 ? 'review encontrada' : 'reviews encontradas'}
                  </p>
                  <ReviewTable onSelect={handleSelectReview} reviews={reviews} selectedReviewId={selectedReviewId} />
                </>
              ) : (
                <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
                  <Inbox aria-hidden="true" className="mx-auto text-slate-400" size={34} />
                  <h2 className="mt-3 font-semibold text-slate-800">
                    {hasActiveCriteria ? 'No hay reviews que coincidan' : 'Todavía no hay reviews'}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {hasActiveCriteria ? 'Prueba con otros términos o ajusta los filtros.' : 'Las reviews importadas aparecerán en esta sección.'}
                  </p>
                </div>
              )
            )}
          </section>
          {showDetail && (
            <ReviewDetail
              detailAnchorRef={detailAnchor}
              canClassify={canClassify}
              canDetectTopic={canDetectTopic}
              canPrioritize={canPrioritize}
              canSuggest={canPrioritize}
              onSuggested={handleSuggested}
              onReload={() => setReloadKey((value) => value + 1)}
              error={selectedDetailError}
              isLoading={isDetailLoading || (selectedReviewId !== null && !selectedDetail && !selectedDetailError)}
              isStatusSaving={isStatusSaving}
              onEdit={handleEdit}
              onClassified={handleClassified}
              onRetry={() => setDetailReloadKey((value) => value + 1)}
              onStatusConfirm={handleStatusConfirm}
              onSummarySaved={handleSummarySaved}
              onSolutionSaved={handleSolutionSaved}
              onTopicDetected={handleTopicDetected}
              onPrioritized={handlePrioritized}
              review={selectedDetail}
              statusFeedback={statusFeedback?.reviewId === selectedReviewId ? statusFeedback : null}
            />
          )}
        </div>
      </div>

      {editingReview && (
        <ReviewEditForm
          key={editingReview.id}
          onCancel={() => setEditingReview(null)}
          onSaved={handleSaved}
          review={editingReview}
        />
      )}
    </main>
  )
}

export default ReviewsPage
