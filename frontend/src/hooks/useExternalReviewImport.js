import { useCallback, useEffect, useRef, useState } from 'react'
import { getStoredSession } from '../services/authService.js'
import { getExternalReviewConnections, importExternalReviews } from '../services/importService.js'
import { externalConnectionsError, externalImportFailure, externalImportIdentity, externalImportStorageKey } from '../utils/externalReviewImport.js'

function readSession() {
  try { return getStoredSession() } catch { return null }
}

function sameSession(expected) {
  const current = readSession()
  return Boolean(expected && current?.access_token === expected.access_token
    && externalImportIdentity(current) === externalImportIdentity(expected))
}

function safety(identity, business) {
  if (!identity || !business) return { blocked: false, unavailable: false }
  try {
    return { blocked: window.sessionStorage.getItem(externalImportStorageKey(identity, business)) !== null, unavailable: false }
  } catch { return { blocked: true, unavailable: true } }
}

export default function useExternalReviewImport() {
  const [session, setSession] = useState(readSession)
  const identity = externalImportIdentity(session)
  const [discovery, setDiscovery] = useState({ context: null, loading: false, error: '', data: null })
  const [selected, setSelected] = useState('')
  const [operation, setOperation] = useState(null)
  const [importing, setImporting] = useState(false)
  const mounted = useRef(false)
  const listing = useRef(null)
  const sending = useRef(null)
  // Ocultar el contexto anterior durante el render, antes de los efectos o del GET.
  const contextIsCurrent = Boolean(identity) && sameSession(session)
  const currentDiscovery = contextIsCurrent && discovery.context === session
    ? discovery : { loading: false, error: '', data: null }

  const refresh = useCallback(async () => {
    if (!identity || sending.current || !sameSession(session)) return
    listing.current?.abort()
    const controller = new AbortController()
    listing.current = controller
    setDiscovery({ context: session, loading: true, error: '', data: null })
    try {
      const data = await getExternalReviewConnections({ signal: controller.signal })
      if (mounted.current && listing.current === controller && !controller.signal.aborted && sameSession(session)) {
        setDiscovery({ context: session, loading: false, error: '', data })
      }
    } catch (error) {
      if (mounted.current && listing.current === controller && !controller.signal.aborted && sameSession(session)) {
        setDiscovery({ context: session, loading: false, error: externalConnectionsError(error), data: null })
      }
    }
  }, [identity, session])

  useEffect(() => {
    mounted.current = true
    setSelected('')
    setOperation(null)
    setImporting(false)
    setDiscovery({ context: session, loading: false, error: '', data: null })
    void refresh()
    return () => {
      mounted.current = false
      listing.current?.abort()
      sending.current?.abort()
      sending.current = null
      // Cancelar la espera del navegador no cancela el trabajo del servidor.
    }
  }, [refresh, session])

  useEffect(() => {
    function updateSession(event) {
      if (event.key === null || ['gestor_reviews_access_token', 'gestor_reviews_user'].includes(event.key)) setSession(readSession())
    }
    window.addEventListener('storage', updateSession)
    return () => window.removeEventListener('storage', updateSession)
  }, [])

  function select(business) {
    if (sending.current) return
    setSelected(business)
    setOperation(null)
  }

  async function submit(event) {
    event.preventDefault()
    const option = currentDiscovery.data?.connections.find((row) => row.business_data_id === selected)
    if (!identity || !sameSession(session) || sending.current || !currentDiscovery.data?.import_enabled
      || currentDiscovery.loading || option?.status !== 'available' || safety(identity, selected).blocked) return
    const key = externalImportStorageKey(identity, selected)
    try {
      window.sessionStorage.setItem(key, 'pending')
      if (window.sessionStorage.getItem(key) !== 'pending') throw new Error('Protección no disponible')
    } catch {
      setOperation({ context: session, value: { kind: 'error', message: 'El navegador no permite proteger esta operación. No se envió la solicitud.', requiresReview: true, notSent: true } })
      return
    }
    const controller = new AbortController()
    sending.current = controller
    setImporting(true)
    setOperation(null)
    try {
      const result = await importExternalReviews(selected, { signal: controller.signal })
      if (!mounted.current || sending.current !== controller || controller.signal.aborted || !sameSession(session)) return
      let requiresReview = result.control_status === 'reconciliation_required'
      if (!requiresReview) {
        try { window.sessionStorage.removeItem(key) } catch { requiresReview = true }
      }
      setOperation({ context: session, value: { kind: 'success', result, requiresReview } })
    } catch (error) {
      if (!mounted.current || sending.current !== controller || controller.signal.aborted || !sameSession(session)) return
      const failure = externalImportFailure(error)
      if (!failure.requiresReview) {
        try { window.sessionStorage.removeItem(key) } catch { failure.requiresReview = true }
      }
      setOperation({ context: session, value: { kind: 'error', ...failure } })
    } finally {
      if (sending.current === controller) {
        sending.current = null
        if (mounted.current && sameSession(session)) setImporting(false)
      }
    }
  }

  return {
    authorized: contextIsCurrent, loading: currentDiscovery.loading, error: currentDiscovery.error, data: currentDiscovery.data,
    selected, select, operation: contextIsCurrent && operation?.context === session ? operation.value : null,
    importing: currentDiscovery === discovery && importing,
    safety: safety(identity, selected), refresh, submit,
  }
}
