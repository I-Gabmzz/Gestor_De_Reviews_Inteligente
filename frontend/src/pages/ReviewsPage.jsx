import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, Download, Inbox, MessageSquarePlus, RefreshCw, RotateCcw, Search, Star, X } from 'lucide-react'
import { Link, useLocation, useNavigate, useNavigationType, useSearchParams } from 'react-router-dom'

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
import './ReviewsPage.css'


const emptyFilters = {
  fecha_desde: '',
  fecha_hasta: '',
  puntuacion: '',
  estado: '',
  fuente: '',
  urgente: '',
}
const scores = ['1', '2', '3', '4', '5']

const filterControlClassName = 'w-full min-w-0'


function getErrorMessage(error) {
  if (error.response?.status === 401) {
    return 'Tu sesión no es válida. Inicia sesión nuevamente.'
  }
  if (error.response?.status === 403) {
    return 'No tienes permiso para consultar las reseñas. Si tu acceso cambió, vuelve a iniciar sesión.'
  }
  if (error.response?.status === 422) {
    return 'Revisa las fechas y los filtros seleccionados e inténtalo nuevamente.'
  }
  return 'No pudimos cargar las reseñas. Intenta nuevamente.'
}

function getStatusErrorMessage(error) {
  if (!error.response) {
    return 'No pudimos confirmar el cambio. Se muestra el último estado confirmado. Intenta nuevamente.'
  }
  if (error.response?.status === 401) {
    return 'Tu sesión expiró. Inicia sesión nuevamente para cambiar el estado.'
  }
  if (error.response?.status === 403) {
    return 'Tu cuenta no tiene permiso para cambiar el estado de esta reseña.'
  }
  if (error.response?.status === 404) {
    return 'La reseña ya no está disponible. Actualiza la lista e inténtalo de nuevo.'
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
  if (error.response?.status === 403) return 'No tienes permiso para exportar las reseñas.'
  if (error.response?.status === 422) return 'Revisa los filtros antes de exportar.'
  if (!error.response) return 'No pudimos conectar con el servidor para exportar. Inténtalo nuevamente.'
  return 'No pudimos exportar las reseñas. Intenta nuevamente.'
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

function focusDetailPanel(panel) {
  panel?.scrollIntoView?.({ block: 'start', behavior: 'auto' })
  panel?.focus({ preventScroll: true })
}

function isRenderedTarget(element) {
  if (!element?.isConnected || element.closest('[hidden], [aria-hidden="true"]')) return false
  for (let current = element; current; current = current.parentElement) {
    const style = window.getComputedStyle(current)
    if (style.display === 'none' || style.visibility === 'hidden') return false
  }
  return true
}

function ReviewsPage() {
  const navigationType = useNavigationType()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const currentParams = useRef(searchParams)
  const requestedValue = searchParams.get('review')
  const requestedReviewId = /^[1-9]\d*$/.test(requestedValue || '') && Number.isSafeInteger(Number(requestedValue)) ? Number(requestedValue) : null
  const requestedReviewRef = useRef(requestedReviewId)
  const detailAnchor = useRef(null)
  const searchInput = useRef(null)
  const keyboardSelection = useRef(null)
  const firstFilter = useRef(null)
  const listFocusAnchor = useRef(null)
  const generalErrorAnchor = useRef(null)
  const exportErrorAnchor = useRef(null)
  const previousGeneralError = useRef('')
  const previousExportError = useRef('')
  const returnContext = useRef(null)
  const previousRequestedReviewId = useRef(requestedReviewId)
  const [reviews, setReviews] = useState([])
  const searchText = searchParams.get('busqueda') ?? ''
  const sourceText = searchParams.get('fuente') ?? ''
  const [debouncedSearch, setDebouncedSearch] = useState(searchText)
  const [debouncedSource, setDebouncedSource] = useState(sourceText)
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
  const dateFrom = searchParams.get('fecha_desde')
  const dateTo = searchParams.get('fecha_hasta')
  const score = searchParams.get('puntuacion')
  const status = searchParams.get('estado')
  const urgency = searchParams.get('urgente')
  const urgentOnly = urgency === 'true'
  const invalidFilters = (urgency !== null && urgency !== 'true' && urgency !== 'false')
    || (status !== null && !REVIEW_STATUS_OPTIONS.some(({ value }) => value === status))
    || (score !== null && !scores.includes(score))
    || [dateFrom, dateTo].some((date) => date !== null && !/^\d{4}-\d{2}-\d{2}$/.test(date))
  const hasActiveFilters = invalidFilters || urgentOnly || Boolean(dateFrom || dateTo || score || status || sourceText.trim())
  const appliedSearch = navigationType === 'REPLACE' ? debouncedSearch : searchText
  const appliedSource = navigationType === 'REPLACE' ? debouncedSource : sourceText
  const hasActiveCriteria = Boolean(appliedSearch.trim()) || hasActiveFilters
  const session = getStoredSession()
  const tenantId = session?.user?.tenant_id
  const canClassify = canClassifyReview(session)
  const canPrioritize = canPrioritizeReview(session)
  const canExport = canAccessRoute(session?.user?.rol, '/reviews')
  const selectedDetail = selectedReview?.id === selectedReviewId ? selectedReview : null
  const selectedDetailError = detailError?.reviewId === selectedReviewId ? detailError.message : ''
  const showDetail = selectedReviewId !== null || (!isLoading && !errorMessage && reviews.length > 0)
  const detailMotion = useRef(null)

  useEffect(() => {
    const panel = detailMotion.current
    if (selectedDetail?.id == null || !panel?.animate || window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches) return
    const animation = panel.animate([{ opacity: .78, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }], {
      duration: 240,
      easing: 'cubic-bezier(.2,.75,.25,1)',
    })
    return () => animation.cancel()
  }, [selectedDetail?.id])

  useLayoutEffect(() => {
    currentParams.current = searchParams
  }, [searchParams])

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
    requestedReviewRef.current = requestedReviewId
    if (requestedReviewId === null) return
    if (!location.state?.reviewsReturn) returnContext.current = null
    setSelectedReviewId(requestedReviewId)
    setStatusFeedback(null)
  }, [requestedReviewId, location.state])

  useEffect(() => {
    const keyboardRequest = keyboardSelection.current
    const focusId = keyboardRequest?.reviewId ?? requestedReviewId
    if (focusId === null || focusId !== selectedReviewId || isDetailLoading) return
    if (selectedReview?.id !== focusId && !selectedDetailError) return
    keyboardSelection.current = null
    if (keyboardRequest && document.activeElement !== keyboardRequest.trigger && document.activeElement !== document.body) return
    focusDetailPanel(detailAnchor.current)
  }, [requestedReviewId, selectedReviewId, selectedReview?.id, selectedDetailError, isDetailLoading])
  useLayoutEffect(() => {
    if (requestedReviewId !== null) { previousRequestedReviewId.current = requestedReviewId; return }
    if (previousRequestedReviewId.current === null || isLoading) return
    previousRequestedReviewId.current = null
    const context = returnContext.current
    window.scrollTo(0, context?.scrollY ?? 0)
    const target = context?.reviewId ? [...document.querySelectorAll(`[data-review-id="${context.reviewId}"]`)].find(isRenderedTarget) : null
    ;(target || (isRenderedTarget(context?.triggerElement) ? context.triggerElement : null) || listFocusAnchor.current)?.focus({ preventScroll: true })
  }, [requestedReviewId, isLoading, reviews])

  useLayoutEffect(() => {
    if (errorMessage && previousGeneralError.current !== errorMessage) generalErrorAnchor.current?.focus({ preventScroll: true })
    previousGeneralError.current = errorMessage
  }, [errorMessage])
  useLayoutEffect(() => {
    if (exportError && previousExportError.current !== exportError) exportErrorAnchor.current?.focus({ preventScroll: true })
    previousExportError.current = exportError
  }, [exportError])

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

  function updateCriteria(values) {
    const next = new URLSearchParams(currentParams.current)
    for (const [name, value] of Object.entries(values)) {
      if (value) next.set(name, value)
      else next.delete(name)
    }
    currentParams.current = next
    setSearchParams(next, { replace: true })
  }

  function handleFilterChange({ target }) {
    updateCriteria({ [target.name]: target.value })
  }

  function clearCriteria({ search = false, filters = false }) {
    if (search) setDebouncedSearch('')
    if (filters) setDebouncedSource('')
    updateCriteria({ ...(search ? { busqueda: '' } : {}), ...(filters ? emptyFilters : {}) })
    if (filters && !search) firstFilter.current?.focus()
    else searchInput.current?.focus()
  }

  useEffect(() => {
    if (navigationType !== 'REPLACE') {
      setDebouncedSearch(searchText)
      return
    }
    const timeout = setTimeout(() => setDebouncedSearch(searchText), 400)
    return () => clearTimeout(timeout)
  }, [searchText, navigationType])

  useEffect(() => {
    if (navigationType !== 'REPLACE') {
      setDebouncedSource(sourceText)
      return
    }
    const timeout = setTimeout(() => setDebouncedSource(sourceText), 400)
    return () => clearTimeout(timeout)
  }, [sourceText, navigationType])

  useEffect(() => {
    if (invalidFilters) {
      setIsLoading(false)
      setErrorMessage('El enlace contiene filtros no válidos. Revísalos o usa «Limpiar filtros».')
      setListedCriteria(null)
      return
    }
    const controller = new AbortController()

    async function loadReviews() {
      setIsLoading(true)
      setErrorMessage('')

      try {
        const criteria = {
          busqueda: appliedSearch,
          fecha_desde: dateFrom,
          fecha_hasta: dateTo,
          puntuacion: score,
          estado: status,
          fuente: appliedSource,
          urgente: urgentOnly,
        }
        const data = await getReviews(criteria, { signal: controller.signal })
        if (controller.signal.aborted) return
        const criteriaKey = JSON.stringify(criteria)
        const keepDetail = (id) => id === requestedReviewRef.current
          || (retainedDetail.current?.id === id && retainedDetail.current.criteriaKey === criteriaKey)
        setListedCriteria(criteria)
        setReviews(data.items)
        setSelectedReviewId((currentId) => {
          if (requestedReviewRef.current !== null) return requestedReviewRef.current
          if (currentId === null) return data.items[0]?.id ?? null
          return keepDetail(currentId) || data.items.some((review) => review.id === currentId)
            ? currentId
            : data.items[0]?.id ?? null
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
  }, [appliedSearch, appliedSource, dateFrom, dateTo, score, status, urgentOnly, invalidFilters, reloadKey, listReloadKey])

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
    refreshListKeepingDetail(updatedReview.id)
    setEditingReview(null)
    setErrorMessage('')
    setStatusFeedback(null)
    setSuccessMessage('Cambios guardados.')
  }

  function refreshListKeepingDetail(reviewId) {
    retainedDetail.current = { id: reviewId, criteriaKey: JSON.stringify(listedCriteria) }
    setListReloadKey((value) => value + 1)
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
      setSelectedReview((current) => (
        current?.id === reviewId && current.tenant_id === reviewTenantId ? { ...current, estado: updatedReview.estado } : current
      ))
      setStatusFeedback({ reviewId, kind: 'success', message: 'Estado guardado.' })
      refreshListKeepingDetail(reviewId)
      return true
    } catch (error) {
      setStatusFeedback({ reviewId, kind: 'error', message: getStatusErrorMessage(error) })
      return false
    } finally {
      statusSavePending.current = false
      setIsStatusSaving(false)
    }
  }

  function handleSelectReview(reviewId, triggerElement) {
    const openingFromList = requestedReviewId === null
    if (openingFromList || location.state?.reviewsReturn) returnContext.current = { reviewId, scrollY: window.scrollY, triggerElement }
    if (reviewId !== selectedReviewId) { retainedDetail.current = null; setStatusFeedback(null) }
    keyboardSelection.current = triggerElement ? { reviewId, trigger: triggerElement } : null
    if (triggerElement && reviewId === selectedReviewId && detailAnchor.current) { keyboardSelection.current = null; focusDetailPanel(detailAnchor.current) }
    setSelectedReviewId(reviewId)
    setSearchParams((current) => {
      current.set('review', String(reviewId))
      return current
    }, {
      replace: !openingFromList,
      state: openingFromList ? { reviewsReturn: true } : location.state,
    })
  }

  function handleReturnToList() {
    if (location.state?.reviewsReturn) {
      navigate(-1)
      return
    }
    setSearchParams((current) => {
      current.delete('review')
      return current
    }, { replace: true, state: null })
  }

  async function handleExport() {
    if (exportPending.current || !listedCriteria || isLoading || errorMessage || invalidFilters) return
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

  const visibleScores = reviews.map(({ puntuacion }) => puntuacion).filter(Number.isFinite)
  const averageScore = visibleScores.length
    ? new Intl.NumberFormat('es-MX', { maximumFractionDigits: 1 }).format(visibleScores.reduce((total, value) => total + value, 0) / visibleScores.length)
    : null
  return (
    <main className="reviews-workspace min-h-screen text-slate-900">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
        <header className="reviews-workspace-header">
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
              aria-disabled={isLoading}
              onClick={() => { if (!isLoading) setReloadKey((value) => value + 1) }}
              type="button"
            >
              <RefreshCw aria-hidden="true" className={isLoading ? 'motion-safe:animate-spin' : ''} size={16} />
              Actualizar
            </button>
          </div>
          {requestedReviewId === null && !isLoading && !errorMessage && (
            <div className="reviews-workspace-metrics">
              <div className="reviews-metric">
                <span className="reviews-metric-icon"><Inbox aria-hidden="true" size={20} /></span>
                <div><p>Reseñas en esta vista</p><strong>{reviews.length}</strong></div>
              </div>
              <div className="reviews-metric">
                <span className="reviews-metric-icon"><Star aria-hidden="true" size={20} /></span>
                <div><p>Puntuación de esta vista</p><strong>{averageScore === null ? 'Sin datos' : `${averageScore} / 5`}</strong></div>
              </div>
            </div>
          )}
        </header>

        <section aria-label="Búsqueda y filtros de reseñas" className={`mt-6 ${requestedReviewId !== null ? 'hidden xl:flex' : 'flex'} flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4 sm:p-5`}>
          <div className="w-full min-w-0 sm:max-w-md">
            <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-search">
              Buscar reseñas
            </label>
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                className="w-full"
                id="review-search"
                inputMode="search"
                name="busqueda"
                onChange={handleFilterChange}
                placeholder="Por comentario, autor o tema"
                ref={searchInput}
                type="text"
                value={searchText}
              />
              {searchText && (
                <button
                  aria-label="Limpiar búsqueda"
                  className="absolute right-0.5 top-1/2 grid size-11 -translate-y-1/2 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600"
                  onClick={() => clearCriteria({ search: true })}
                  title="Limpiar búsqueda"
                  type="button"
                >
                  <X aria-hidden="true" size={18} />
                </button>
              )}
            </div>
          </div>
          <div className="w-full border-t border-slate-200 pt-4">
            <div className="mb-3 flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-800">Filtros</h2>
                {hasActiveFilters && <span className="text-xs font-medium text-sky-700">Filtros activos</span>}
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  className="workspace-action"
                  disabled={!hasActiveFilters}
                  onClick={() => clearCriteria({ filters: true })}
                  type="button"
                >
                  <RotateCcw aria-hidden="true" size={16} />
                  Limpiar filtros
                </button>
                {canExport && (
                  <button
                    aria-busy={isExporting}
                    className="workspace-action"
                    disabled={isExporting || isLoading || !listedCriteria || Boolean(errorMessage) || invalidFilters}
                    onClick={handleExport}
                    type="button"
                  >
                    <Download aria-hidden="true" size={16} />
                    {isExporting ? 'Exportando CSV…' : 'Exportar CSV'}
                  </button>
                )}
              </div>
            </div>
            <label className="mb-3 inline-flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold text-slate-800">
              <input
                checked={urgentOnly}
                className="size-4 accent-sky-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                name="urgente"
                onChange={(event) => updateCriteria({ urgente: event.target.checked ? 'true' : '' })}
                type="checkbox"
              />
              Urgentes
            </label>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-fecha-desde">Desde</label>
                <input className={filterControlClassName} id="review-fecha-desde" name="fecha_desde" onChange={handleFilterChange} ref={firstFilter} type="date" value={dateFrom ?? ''} />
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-fecha-hasta">Hasta</label>
                <input className={filterControlClassName} id="review-fecha-hasta" name="fecha_hasta" onChange={handleFilterChange} type="date" value={dateTo ?? ''} />
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-puntuacion">Puntuación</label>
                <select className={filterControlClassName} id="review-puntuacion" name="puntuacion" onChange={handleFilterChange} value={score ?? ''}>
                  <option value="">Todas</option>
                  {scores.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-estado">Estado</label>
                <select className={filterControlClassName} id="review-estado" name="estado" onChange={handleFilterChange} value={status ?? ''}>
                  <option value="">Todos los estados</option>
                  {REVIEW_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </div>
              <div className="min-w-0">
                <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-fuente">Fuente</label>
                <input className={filterControlClassName} id="review-fuente" name="fuente" onChange={handleFilterChange} placeholder="Cualquier fuente" type="text" value={sourceText} />
              </div>
            </div>
          </div>
        </section>

        {requestedReviewId !== null && (
          <button
            className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 xl:hidden"
            onClick={handleReturnToList}
            type="button"
          >
            <ArrowLeft aria-hidden="true" size={16} />
            Volver a resultados
          </button>
        )}

        {exportError && (
          <div ref={exportErrorAnchor} tabIndex={-1} className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700" role="alert">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
            {exportError}
          </div>
        )}

        {errorMessage && (
          <div ref={generalErrorAnchor} tabIndex={-1} className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700" role="alert">
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
          <section ref={listFocusAnchor} tabIndex={-1} aria-label="Listado de reviews" aria-labelledby="reviews-list-title" className={`min-w-0 ${requestedReviewId !== null ? 'hidden xl:block' : ''}`} aria-busy={isLoading}>
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="text-lg font-semibold tracking-tight" id="reviews-list-title">Bandeja</h2>
              {!isLoading && !errorMessage && reviews.length > 0 && (
                <p className="text-sm text-slate-600" role="status">
                  {reviews.length} {reviews.length === 1 ? 'reseña' : 'reseñas'}
                </p>
              )}
            </div>
            {isLoading && (
              <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500" role="status">
                Cargando reseñas…
              </p>
            )}
            {!isLoading && !errorMessage && (
              reviews.length > 0 ? (
                <ReviewTable onSelect={handleSelectReview} reviews={reviews} selectedReviewId={selectedReviewId} />
              ) : (
                <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
                  <Inbox aria-hidden="true" className="mx-auto text-slate-400" size={34} />
                  <h3 className="mt-3 font-semibold text-slate-800">
                    {hasActiveCriteria ? 'No encontramos reseñas' : 'Aún no hay reseñas'}
                  </h3>
                  {hasActiveCriteria ? (
                    <button
                      className="workspace-action mt-3"
                      onClick={() => clearCriteria({ search: true, filters: true })}
                      type="button"
                    >
                      Limpiar búsqueda y filtros
                    </button>
                  ) : (
                    <p className="mt-1 text-sm text-slate-600">Las reseñas de este negocio aparecerán aquí.</p>
                  )}
                </div>
              )
            )}
          </section>
          {showDetail && (
            <div ref={detailMotion} className={requestedReviewId === null ? 'hidden xl:block' : 'min-w-0'}><ReviewDetail
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
            /></div>
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
