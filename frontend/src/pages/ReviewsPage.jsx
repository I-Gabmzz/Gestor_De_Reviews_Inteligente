import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, Download, Inbox, MessageSquarePlus, MessageSquareText, RefreshCw, RotateCcw, Search, X } from 'lucide-react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import { exportReviews, getReviewById, getReviews, updateReviewStatus } from '../services/reviewService.js'
import ReviewDetail from '../components/reviews/ReviewDetail.jsx'
import ReviewEditForm from '../components/reviews/ReviewEditForm.jsx'
import ReviewTable from '../components/reviews/ReviewTable.jsx'
import { REVIEW_STATUS_OPTIONS } from '../utils/reviewStatus.js'
import { getStoredSession } from '../services/authService.js'
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

const filterControlClassName = 'w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none focus:border-sky-500 focus:ring-4 focus:ring-sky-100'


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
    return 'No pudimos conectar con el servidor. El estado anterior se conserva; inténtalo nuevamente.'
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
  return 'No fue posible guardar el estado. Inténtalo nuevamente.'
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

function isRenderedTarget(element) {
  if (!element?.isConnected || element.closest('[hidden], [aria-hidden="true"]')) return false
  for (let current = element; current; current = current.parentElement) {
    const style = window.getComputedStyle(current)
    if (style.display === 'none' || style.visibility === 'hidden') return false
  }
  return true
}

function ReviewsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedValue = searchParams.get('review')
  const requestedReviewId = /^[1-9]\d*$/.test(requestedValue || '') && Number.isSafeInteger(Number(requestedValue)) ? Number(requestedValue) : null
  const detailAnchor = useRef(null)
  const listFocusAnchor = useRef(null)
  const generalErrorAnchor = useRef(null)
  const exportErrorAnchor = useRef(null)
  const previousGeneralError = useRef('')
  const previousExportError = useRef('')
  const returnContext = useRef(null)
  const pendingListOpening = useRef(null)
  const previousRequestedReviewId = useRef(requestedReviewId)
  const requestedReviewIdRef = useRef(requestedReviewId)
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
  const [statusError, setStatusError] = useState(null)
  const [isStatusSaving, setIsStatusSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [editingReview, setEditingReview] = useState(null)
  const [successMessage, setSuccessMessage] = useState('')
  const [listedCriteria, setListedCriteria] = useState(null)
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const exportPending = useRef(false)
  const { fecha_desde, fecha_hasta, puntuacion, estado } = filters
  const hasActiveFilters = Object.values(filters).some(Boolean)
  const hasActiveCriteria = Boolean(debouncedSearch.trim()) || Object.values(filters).some((value) => Boolean(value.trim()))
  const canClassify = canClassifyReview(getStoredSession())
  const canPrioritize = canPrioritizeReview(getStoredSession())
  const canExport = canAccessRoute(getStoredSession()?.user?.rol, '/reviews')

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
    requestedReviewIdRef.current = requestedReviewId
  }, [requestedReviewId])

  useEffect(() => {
    if (requestedReviewId === null) return
    if (location.state?.reviewsReturn) {
      if (pendingListOpening.current === requestedReviewId) pendingListOpening.current = null
    } else if (pendingListOpening.current !== requestedReviewId) {
      returnContext.current = null
    }
    setSelectedReviewId(requestedReviewId)
    setStatusError(null)
    setErrorMessage('')
  }, [requestedReviewId, location.state])

  useLayoutEffect(() => {
    if (requestedReviewId === null) return
    if (errorMessage) return
    detailAnchor.current?.scrollIntoView?.({ block: 'start', behavior: 'auto' })
    detailAnchor.current?.focus({ preventScroll: true })
  }, [requestedReviewId, selectedReviewId, selectedReview?.id, isDetailLoading, errorMessage])

  useLayoutEffect(() => {
    if (!errorMessage) {
      previousGeneralError.current = ''
      return
    }
    if (previousGeneralError.current === errorMessage) return
    previousGeneralError.current = errorMessage
    generalErrorAnchor.current?.focus({ preventScroll: true })
  }, [errorMessage])

  useLayoutEffect(() => {
    if (!exportError) {
      previousExportError.current = ''
      return
    }
    if (previousExportError.current === exportError) return
    previousExportError.current = exportError
    exportErrorAnchor.current?.focus({ preventScroll: true })
  }, [exportError])

  useLayoutEffect(() => {
    if (requestedReviewId !== null) {
      previousRequestedReviewId.current = requestedReviewId
      return
    }
    if (previousRequestedReviewId.current === null || isLoading) return

    previousRequestedReviewId.current = null
    pendingListOpening.current = null
    const context = returnContext.current
    window.scrollTo(0, context?.scrollY ?? 0)
    const currentTrigger = context?.reviewId
      ? [...document.querySelectorAll(`[data-review-id="${context.reviewId}"]`)]
        .find(isRenderedTarget)
      : null
    const target = currentTrigger
      || (isRenderedTarget(context?.triggerElement) ? context.triggerElement : null)
      || listFocusAnchor.current
      || generalErrorAnchor.current
      || exportErrorAnchor.current
    target?.focus({ preventScroll: true })
  }, [requestedReviewId, isLoading, reviews, selectedReviewId, errorMessage])

  function handleClassified(result) {
    setSelectedReview((current) => mergeClassification(current, result))
    setReviews((current) => current.map((review) => mergeClassification(review, result)))
  }
  const canDetectTopic = canAccessRoute(getStoredSession()?.user?.rol, '/reviews')

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
        setListedCriteria(criteria)
        setReviews(data.items)
        setSelectedReviewId((currentId) => {
          if (requestedReviewIdRef.current !== null) return requestedReviewIdRef.current
          if (currentId === null) return data.items[0]?.id ?? null
          return data.items.some((review) => review.id === currentId) ? currentId : null
        })
        setSelectedReview((current) => {
          if (current === null) return null
          if (current.id === requestedReviewIdRef.current) return current
          return data.items.find((review) => review.id === current.id) ?? null
        })
      } catch (error) {
        if (!controller.signal.aborted && error.code !== 'ERR_CANCELED') {
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
  }, [debouncedSearch, debouncedSource, fecha_desde, fecha_hasta, puntuacion, estado, reloadKey])

  useEffect(() => {
    if (selectedReviewId === null) {
      setSelectedReview(null)
      setIsDetailLoading(false)
      return undefined
    }

    const controller = new AbortController()

    async function loadReviewDetail() {
      setIsDetailLoading(true)
      try {
        const data = await getReviewById(selectedReviewId, { signal: controller.signal })
        if (controller.signal.aborted) return
        setSelectedReview(data)
      } catch (error) {
        if (!controller.signal.aborted && error.code !== 'ERR_CANCELED') {
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
  }, [selectedReviewId, reloadKey])

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
    setStatusError(null)
    setSuccessMessage('Los cambios de la review se guardaron correctamente.')
  }

  async function handleStatusConfirm(estado) {
    if (!selectedReview || isStatusSaving) {
      return false
    }

    const reviewId = selectedReview.id
    setIsStatusSaving(true)
    setStatusError(null)
    setSuccessMessage('')

    try {
      const updatedReview = await updateReviewStatus(reviewId, estado)
      setSelectedReview((current) => current?.id === reviewId ? updatedReview : current)
      setReloadKey((value) => value + 1)
      return true
    } catch (error) {
      setStatusError({ reviewId, message: getStatusErrorMessage(error) })
      return false
    } finally {
      setIsStatusSaving(false)
    }
  }

  function handleSelectReview(reviewId, triggerElement) {
    const openingFromList = requestedReviewId === null
    if (openingFromList || location.state?.reviewsReturn) {
      returnContext.current = {
        reviewId,
        scrollY: window.scrollY,
        triggerElement,
      }
    }
    if (openingFromList) pendingListOpening.current = reviewId
    setStatusError(null)
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
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Reviews de clientes</h1>
            <p className="mt-2 text-sm text-slate-600">
              Consulta los comentarios registrados para tu organización.
            </p>
          </div>
          <div className={`flex flex-col gap-2 sm:flex-row ${requestedReviewId !== null ? 'hidden xl:flex' : ''}`}>
            <Link
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1d1d1f] px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#333336] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 sm:w-auto"
              to="/reviews/new"
            >
              <MessageSquarePlus aria-hidden="true" size={16} />
              Registrar review
            </Link>
            <button
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              disabled={isLoading}
              onClick={() => setReloadKey((value) => value + 1)}
              type="button"
            >
              <RefreshCw aria-hidden="true" className={isLoading ? 'animate-spin' : ''} size={16} />
              Actualizar
            </button>
          </div>
        </div>

        <section
          aria-label="Búsqueda y filtros de reviews"
          className={`mt-6 flex flex-col gap-3 ${requestedReviewId !== null ? 'hidden xl:flex' : ''}`}
        >
          <div className="w-full min-w-0 sm:max-w-md">
            <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="review-search">
              Buscar por contenido
            </label>
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-10 pr-11 text-sm text-slate-900 shadow-sm outline-none placeholder:text-slate-400 focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
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
                  className="absolute right-0.5 top-1/2 grid size-11 -translate-y-1/2 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600"
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
            <div className="mb-3 flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-800">Filtros</h2>
                {hasActiveFilters && <span className="text-xs font-medium text-sky-700">Filtros activos</span>}
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
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
                    className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#10233f] px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
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

        {isLoading && requestedReviewId === null && reviews.length === 0 && (
          <div ref={listFocusAnchor} tabIndex={-1} className="mt-6 rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600" aria-live="polite">
            Cargando reviews…
          </div>
        )}

        {!isLoading && !errorMessage && requestedReviewId === null && reviews.length === 0 && (
          <div ref={listFocusAnchor} tabIndex={-1} className="mt-6 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600">
            <Inbox aria-hidden="true" className="mx-auto text-slate-400" size={34} />
            <h2 className="mt-3 font-semibold text-slate-800">
              {hasActiveCriteria ? 'No hay reviews que coincidan' : 'Todavía no hay reviews'}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {hasActiveCriteria ? 'Prueba con otros términos o ajusta los filtros.' : 'Las reviews importadas aparecerán en esta sección.'}
            </p>
          </div>
        )}

        {!errorMessage && (reviews.length > 0 || requestedReviewId !== null) && (
          <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_440px]">
            <section
              ref={listFocusAnchor}
              aria-label="Listado de reviews"
              className={`min-w-0 ${requestedReviewId !== null ? 'hidden xl:block' : ''}`}
              tabIndex={-1}
            >
              {isLoading ? (
                <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500" aria-live="polite">
                  Cargando reviews…
                </div>
              ) : reviews.length > 0 ? (
                <>
                  <h2 className="mb-3 text-sm text-slate-500">
                    {reviews.length} {reviews.length === 1 ? 'review encontrada' : 'reviews encontradas'}
                  </h2>
                  <ReviewTable
                    onSelect={handleSelectReview}
                    reviews={reviews}
                    selectedReviewId={selectedReviewId}
                  />
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
              )}
            </section>
            <div className={`min-w-0 ${requestedReviewId === null ? 'hidden xl:block' : ''}`}>
              <ReviewDetail
                detailAnchorRef={detailAnchor}
                canClassify={canClassify}
                canDetectTopic={canDetectTopic}
                canPrioritize={canPrioritize}
                canSuggest={canPrioritize}
                onSuggested={handleSuggested}
                onReload={() => setReloadKey((value) => value + 1)}
                isLoading={isDetailLoading || (selectedReviewId !== null && selectedReview?.id !== selectedReviewId)}
                isStatusSaving={isStatusSaving}
                onEdit={handleEdit}
                onClassified={handleClassified}
                onStatusConfirm={handleStatusConfirm}
                onSummarySaved={handleSummarySaved}
                onSolutionSaved={handleSolutionSaved}
                onTopicDetected={handleTopicDetected}
                onPrioritized={handlePrioritized}
                review={selectedReview}
                statusError={statusError && statusError.reviewId === selectedReview?.id ? statusError.message : ''}
              />
            </div>
          </div>
        )}
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
