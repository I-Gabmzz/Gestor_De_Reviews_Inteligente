import { useCallback, useEffect, useRef, useState } from 'react'
import { Building2, ExternalLink, RefreshCw, UserPlus } from 'lucide-react'
import { getStoredSession } from '../services/authService.js'
import { createBusinessAccount, getBusinessConnections, linkGoogleBusiness, listBusinesses, setGoogleConnection, updateBusiness } from '../services/adminBusinessService.js'

const field = 'min-h-12 w-full min-w-0 rounded-lg border border-[#d2d2d7] bg-[#fafafa] px-3 py-2.5 text-sm focus:border-[#515154] focus:outline-none focus:ring-4 focus:ring-slate-100 disabled:opacity-60'
const primary = 'admin-primary inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#1d1d1f] px-4 py-3 text-sm font-semibold text-white hover:bg-[#333336] disabled:opacity-60'
const secondary = 'inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#d2d2d7] px-3 py-2 text-sm font-semibold hover:bg-[#f5f5f7] disabled:opacity-60'
const emptyAccount = () => ({ mode: 'existing', tenant: '', business_name: '', nombre: '', correo: '', password: '', rol: 'admin_tenant', includeMaps: false, url: '', confirmed: false })
function session() { try { return getStoredSession() } catch { return null } }
function isAdmin(value) { return value?.user?.rol === 'admin_general' && Boolean(value.access_token) }
function same(expected) { const current = session(); return isAdmin(current) && current.access_token === expected?.access_token && current.user.id === expected?.user.id }
function message(error) {
  const status = error.response?.status
  if (status === 403) return 'Tu cuenta no tiene permiso para realizar esta operación.'
  if (!error.response || status >= 500) return 'No pudimos confirmar el resultado. Actualiza la lista y comprueba el negocio y sus cuentas antes de repetir.'
  return typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Revisa los datos del formulario e inténtalo nuevamente.'
}

function BusinessSettings({ business, disabled, save }) {
  const [name, setName] = useState(business.nombre)
  const [confirming, setConfirming] = useState(false)
  const active = business.estado === 'activo'
  const action = active ? 'Desactivar negocio' : 'Reactivar negocio'
  const trimmed = name.trim()

  function rename(event) {
    event.preventDefault()
    if (disabled || !trimmed || trimmed === business.nombre || trimmed.length > 255) return
    save({ nombre: trimmed })
  }

  return (
    <div className="mt-4 space-y-4 rounded-xl border border-[#e5e5ea] p-4">
      <p className="break-words text-sm font-medium">
        {business.nombre} (#{business.id}) · Negocio {active ? 'activo' : 'inactivo'}
      </p>
      <form className="space-y-3" onSubmit={rename}>
        <label className="block space-y-2 text-sm font-medium">
          Nombre del negocio
          <input required maxLength={255} className={field} disabled={disabled} value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <button type="submit" className={secondary} disabled={disabled || !trimmed || trimmed === business.nombre}>Guardar nombre</button>
      </form>
      {confirming ? (
        <div className="space-y-3 border-t border-[#e5e5ea] pt-4">
          <p className="text-sm leading-6">
            {active
              ? `Al desactivar ${business.nombre}, sus cuentas perderán el acceso. Sus reseñas y conexiones de Google se conservarán.`
              : `Al reactivar ${business.nombre}, las cuentas habilitadas podrán iniciar sesión nuevamente.`}
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primary} disabled={disabled} onClick={() => save({ estado: active ? 'inactivo' : 'activo' })}>Confirmar {active ? 'desactivación' : 'reactivación'}</button>
            <button type="button" className={secondary} disabled={disabled} onClick={() => setConfirming(false)}>Cancelar</button>
          </div>
        </div>
      ) : <button type="button" className={secondary} disabled={disabled} onClick={() => setConfirming(true)}>{action}</button>}
    </div>
  )
}

function FieldError({ id, error }) {
  return error ? <p className="mt-2 text-sm text-red-800" id={id} role="alert">{error}</p> : null
}

function OperationResult({ error, notice }) {
  return <>
    {error && <p role="alert" className="wrap-anywhere rounded-lg bg-red-50 p-4 text-sm leading-6 text-red-800">{error}</p>}
    {notice && <p role="status" className="wrap-anywhere rounded-lg bg-emerald-50 p-4 text-sm leading-6 text-emerald-800">{notice}</p>}
  </>
}

export default function AdminBusinessPanel() {
  const [context, setContext] = useState(session)
  const [businesses, setBusinesses] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [feedbackForm, setFeedbackForm] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [account, setAccount] = useState(emptyAccount)
  const [selected, setSelected] = useState('')
  const [catalog, setCatalog] = useState(null)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [url, setUrl] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [revision, setRevision] = useState(0)
  const pending = useRef(null)
  const mounted = useRef(false)
  const authorized = isAdmin(context) && same(context)

  useEffect(() => {
    mounted.current = true
    const update = () => setContext((current) => { const next = session(); return current?.access_token === next?.access_token && current?.user?.id === next?.user?.id && current?.user?.rol === next?.user?.rol ? current : next })
    window.addEventListener('storage', update)
    window.addEventListener('focus', update)
    return () => { mounted.current = false; window.removeEventListener('storage', update); window.removeEventListener('focus', update) }
  }, [])

  const refresh = useCallback(async (signal) => {
    if (!isAdmin(context) || !same(context)) return
    setLoading(true)
    try {
      const rows = await listBusinesses({ signal })
      if (!mounted.current || signal?.aborted || !same(context)) return
      setBusinesses(rows)
      setSelected((current) => rows.some((row) => String(row.id) === current) ? current : String((rows.find((row) => row.estado === 'activo') ?? rows[0])?.id ?? ''))
      setRevision((current) => current + 1)
    } catch (caught) {
      if (mounted.current && !signal?.aborted && same(context)) {
        setFeedbackForm('')
        setError(message(caught))
      }
    } finally { if (mounted.current && same(context) && !signal?.aborted) setLoading(false) }
  }, [context])

  useEffect(() => {
    pending.current = null; setBusy(false); setLoading(false); setCatalogLoading(false)
    setAccount(emptyAccount()); setBusinesses([]); setSelected(''); setCatalog(null); setError(''); setNotice('')
    setFeedbackForm(''); setFieldErrors({})
    const controller = new AbortController()
    void refresh(controller.signal)
    return () => controller.abort()
  }, [refresh])

  useEffect(() => {
    setCatalog(null); setUrl(''); setConfirmed(false)
    setCatalogLoading(false)
    if (!selected || !authorized) return
    const controller = new AbortController()
    setCatalogLoading(true)
    getBusinessConnections(Number(selected), { signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted && mounted.current && same(context)) setCatalog(data)
    }).catch((caught) => {
      if (!controller.signal.aborted && mounted.current && same(context)) {
        setFeedbackForm('')
        setError(message(caught))
      }
    }).finally(() => { if (!controller.signal.aborted && mounted.current && same(context)) setCatalogLoading(false) })
    return () => controller.abort()
  }, [selected, revision, context, authorized])

  function changeAccount(key, value) { setAccount((current) => ({ ...current, [key]: value })); setNotice(''); setError('') }

  function showInvalidField(event) {
    const { id, validationMessage } = event.target
    if (!id || !validationMessage) return
    event.preventDefault()
    setFieldErrors((current) => ({ ...current, [id]: validationMessage }))
    const firstInvalid = Array.from(event.currentTarget.elements).find((control) => control.willValidate && !control.validity.valid)
    if (firstInvalid === event.target) event.target.focus()
  }

  function clearFieldError(event) {
    const { id } = event.target
    if (fieldErrors[id]) setFieldErrors((current) => ({ ...current, [id]: undefined }))
  }

  function fieldProps(id, hint) {
    const describedBy = [hint, fieldErrors[id] && `${id}-error`].filter(Boolean).join(' ')
    return { id, 'aria-invalid': fieldErrors[id] ? true : undefined, 'aria-describedby': describedBy || undefined }
  }

  async function mutate(action, onSuccess, form) {
    if (pending.current || !same(context)) return
    const ticket = Symbol('admin-operation')
    pending.current = ticket; setBusy(true); setError(''); setNotice('')
    setFeedbackForm(form?.id ?? '')
    setFieldErrors({})
    try {
      const result = await action()
      if (mounted.current && same(context)) { onSuccess(result); await refresh() }
    } catch (caught) {
      if (mounted.current && same(context)) {
        const detail = caught.response?.data?.detail
        const issues = {}
        if (form && caught.response?.status === 422 && Array.isArray(detail)) {
          for (const issue of detail) {
            const control = issue?.loc?.[0] === 'body' && form.elements.namedItem(issue.loc[1])
            if (control?.id) issues[control.id] = 'Revisa el valor de este campo.'
          }
        }
        setFieldErrors(issues)
        setError(message(caught))
      }
    } finally {
      if (pending.current === ticket) {
        pending.current = null
        if (mounted.current && same(context)) { setBusy(false); setAccount((current) => ({ ...current, password: '' })) }
      }
    }
  }

  function submitAccount(event) {
    event.preventDefault()
    const payload = { nombre: account.nombre, correo: account.correo, password: account.password, rol: account.rol,
      ...(account.mode === 'new' ? { business_name: account.business_name } : { tenant_id: Number(account.tenant) }),
      ...(account.includeMaps ? { google_maps_url: account.url, confirmed: account.confirmed } : {}) }
    void mutate(() => createBusinessAccount(payload), (result) => {
      setNotice(`Cuenta creada: ${result.user.correo}. Negocio: ${result.tenant.nombre}.${result.connection ? ' Google Maps vinculado.' : ''}`)
      setSelected(String(result.tenant.id)); setAccount(emptyAccount())
    }, event.currentTarget)
  }

  function submitLink(event) {
    event.preventDefault()
    void mutate(() => linkGoogleBusiness({ tenant_id: Number(selected), google_maps_url: url, confirmed }), () => {
      setNotice('Ficha de Google Maps vinculada. Las cuentas del negocio ya pueden usar esta conexión para importar reseñas.')
    }, event.currentTarget)
  }

  if (!authorized) return <p className="text-sm text-red-800" role="alert">Inicia sesión como administrador general para gestionar negocios y conexiones.</p>
  const business = businesses.find((row) => String(row.id) === selected)
  const currentCatalog = catalog?.tenant?.id === Number(selected) ? catalog : null
  const active = businesses.filter((row) => row.estado === 'activo')
  const disabled = busy || loading
  const connectionsDisabled = disabled || business?.estado !== 'activo'

  function saveBusiness(changes) {
    void mutate(() => updateBusiness(business.id, changes), (result) => {
      setBusinesses((rows) => rows.map((row) => row.id === result.id ? result : row))
      setNotice(changes.estado
        ? `${result.nombre} quedó ${result.estado}. ${result.estado === 'activo' ? 'Las cuentas habilitadas ya pueden volver a iniciar sesión.' : 'Sus reseñas y conexiones se conservaron.'}`
        : `Nombre guardado: ${result.nombre}.`)
    })
  }
  return <section aria-labelledby="business-admin-title" className="mt-6 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 id="business-admin-title" className="text-xl font-semibold">Usuarios y negocios</h2>
      <button type="button" className={secondary} disabled={disabled} onClick={() => { setFeedbackForm(''); setError(''); setNotice(''); void refresh() }}><RefreshCw size={16} aria-hidden="true" />Actualizar lista</button>
    </div>
    {loading && <p role="status" className="text-sm text-slate-600">Consultando negocios…</p>}
    {!feedbackForm && <OperationResult error={error} notice={notice} />}
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <section className="admin-surface min-w-0 p-4 sm:p-6">
        <h3 className="flex items-center gap-2 text-lg font-semibold"><span className="admin-icon"><UserPlus size={20} aria-hidden="true" /></span>Crear cuenta de negocio</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">Asigna la cuenta a un negocio existente o crea ambos en un solo paso.</p>
        <form id="admin-account" className="mt-5 space-y-4" onSubmit={submitAccount} onInvalid={showInvalidField} onChange={clearFieldError} aria-busy={busy && feedbackForm === 'admin-account'}>
          <fieldset disabled={disabled} className="min-w-0 space-y-4">
            <div className="admin-account-mode flex flex-wrap gap-1 text-sm">
              <label className="inline-flex items-center gap-2"><input type="radio" name="business-mode" value="existing" checked={account.mode === 'existing'} onChange={() => changeAccount('mode', 'existing')} />Negocio existente</label>
              <label className="inline-flex items-center gap-2"><input type="radio" name="business-mode" value="new" checked={account.mode === 'new'} onChange={() => changeAccount('mode', 'new')} />Nuevo negocio</label>
            </div>
            {account.mode === 'existing' ? <div>
              <label className="block space-y-2 text-sm font-medium">Negocio de la cuenta<select {...fieldProps('admin-account-tenant')} name="tenant_id" required className={field} value={account.tenant} onChange={(event) => changeAccount('tenant', event.target.value)}><option value="">Selecciona un negocio</option>{active.map((row) => <option key={row.id} value={row.id}>{row.nombre}</option>)}</select></label>
              <FieldError id="admin-account-tenant-error" error={fieldErrors['admin-account-tenant']} />
            </div> : <div>
              <label className="block space-y-2 text-sm font-medium">Nombre del nuevo negocio<input {...fieldProps('admin-account-business')} name="business_name" required maxLength={255} className={field} value={account.business_name} onChange={(event) => changeAccount('business_name', event.target.value)} /></label>
              <FieldError id="admin-account-business-error" error={fieldErrors['admin-account-business']} />
            </div>}
            <div>
              <label className="block space-y-2 text-sm font-medium">Nombre de la persona<input {...fieldProps('admin-account-name')} name="nombre" required maxLength={255} autoComplete="name" className={field} value={account.nombre} onChange={(event) => changeAccount('nombre', event.target.value)} /></label>
              <FieldError id="admin-account-name-error" error={fieldErrors['admin-account-name']} />
            </div>
            <div>
              <label className="block space-y-2 text-sm font-medium">Correo de acceso<input {...fieldProps('admin-account-email')} name="correo" required type="email" autoComplete="off" className={field} value={account.correo} onChange={(event) => changeAccount('correo', event.target.value)} /></label>
              <FieldError id="admin-account-email-error" error={fieldErrors['admin-account-email']} />
            </div>
            <div>
              <label className="block space-y-2 text-sm font-medium">Contraseña inicial<input {...fieldProps('admin-account-password', 'admin-account-password-help')} name="password" required type="password" minLength={12} maxLength={1024} autoComplete="new-password" className={field} value={account.password} onChange={(event) => changeAccount('password', event.target.value)} /></label>
              <p className="mt-2 text-xs text-slate-500" id="admin-account-password-help">Mínimo 12 caracteres. Compártela directamente con la persona que usará la cuenta.</p>
              <FieldError id="admin-account-password-error" error={fieldErrors['admin-account-password']} />
            </div>
            <label className="block space-y-2 text-sm font-medium">Permisos de la cuenta<select className={field} value={account.rol} onChange={(event) => changeAccount('rol', event.target.value)}><option value="admin_tenant">Administrador del negocio</option><option value="usuario_negocio">Usuario del negocio</option></select></label>
            <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={account.includeMaps} onChange={(event) => changeAccount('includeMaps', event.target.checked)} />Vincular Google Maps al crear la cuenta</label>
            {account.includeMaps && <div className="space-y-3 rounded-xl bg-[#f5f5f7] p-4">
              <label className="block space-y-2 text-sm font-medium">Enlace de Google Maps para la nueva cuenta<input {...fieldProps('admin-account-maps')} name="google_maps_url" required type="url" maxLength={4096} className={field} placeholder="https://maps.app.goo.gl/…" value={account.url} onChange={(event) => { changeAccount('url', event.target.value); changeAccount('confirmed', false) }} /></label>
              <FieldError id="admin-account-maps-error" error={fieldErrors['admin-account-maps']} />
              <label className="flex items-start gap-2 text-sm"><input {...fieldProps('admin-account-confirm')} name="confirmed" required type="checkbox" className="mt-1" checked={account.confirmed} onChange={(event) => changeAccount('confirmed', event.target.checked)} />Confirmo que esta ficha corresponde al negocio de la cuenta.</label>
              <FieldError id="admin-account-confirm-error" error={fieldErrors['admin-account-confirm']} />
            </div>}
            <p className="text-xs leading-5 text-slate-500">La cuenta verá únicamente las reseñas de su negocio. Si ya está vinculado a Google, usará esa misma conexión.</p>
            <button type="submit" className={primary} disabled={disabled}><UserPlus className="shrink-0" size={17} aria-hidden="true" />{busy && feedbackForm === 'admin-account' ? 'Guardando…' : 'Crear cuenta y asignar negocio'}</button>
          </fieldset>
        </form>
        {feedbackForm === 'admin-account' && <div className="mt-3 space-y-2">
          {busy && <p role="status" className="text-sm text-slate-600">Guardando la cuenta…</p>}
          <OperationResult error={error} notice={notice} />
        </div>}
      </section>
      <section className="admin-surface min-w-0 wrap-anywhere p-4 sm:p-6">
        <h3 className="flex items-center gap-2 text-lg font-semibold"><span className="admin-icon admin-icon-business"><Building2 size={20} aria-hidden="true" /></span>Administrar negocio</h3>
        <label className="mt-5 block space-y-2 text-sm font-medium">Negocio que quieres administrar<select className={field} disabled={disabled} value={selected} onChange={(event) => { setSelected(event.target.value); setError(''); setNotice(''); setFieldErrors({}) }}><option value="">Selecciona un negocio</option>{businesses.map((row) => <option key={row.id} value={row.id}>{row.nombre} (#{row.id}) · {row.estado}</option>)}</select></label>
        {business && <BusinessSettings key={JSON.stringify([business.id, business.nombre, business.estado])} business={business} disabled={disabled} save={saveBusiness} />}
        {business && <h4 className="mt-6 border-t border-[#e5e5ea] pt-5 text-sm font-semibold">Conexiones de Google Maps</h4>}
        {business?.estado === 'inactivo' && <p className="mt-2 text-sm text-slate-600">Reactiva el negocio para gestionar sus conexiones.</p>}
        {catalogLoading && <p className="mt-4 text-sm text-slate-600" role="status">Consultando la conexión…</p>}
        {currentCatalog && <>
          <div className="mt-5 space-y-3">{currentCatalog.connections.length ? currentCatalog.connections.map((row, index) => <div key={row.business_data_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#e5e5ea] p-4">
            <div><p className="text-sm font-semibold">{currentCatalog.tenant.nombre}{currentCatalog.connections.length > 1 ? ` · Conexión ${index + 1}` : ''}</p><p className="mt-1 text-xs text-slate-500">{row.enabled ? 'Importación habilitada' : 'Conexión pausada'}</p><a className="mt-2 inline-flex items-center gap-1 text-sm text-[#515154] underline" href={row.google_maps_url} target="_blank" rel="noreferrer">Ver ficha en Google Maps<ExternalLink size={13} aria-hidden="true" /></a></div>
            <button type="button" className={secondary} disabled={connectionsDisabled} onClick={() => void mutate(() => setGoogleConnection({ tenant_id: Number(selected), business_data_id: row.business_data_id, enabled: !row.enabled }), () => setNotice(row.enabled ? 'Conexión pausada. Las reseñas existentes se conservan.' : 'Conexión habilitada.'))}>{row.enabled ? 'Pausar conexión' : 'Habilitar conexión'}</button>
          </div>) : <p className="text-sm text-slate-600">Este negocio todavía no tiene una ficha vinculada.</p>}</div>
          <form id="admin-link" className="mt-5 space-y-4 border-t border-[#e5e5ea] pt-5" onSubmit={submitLink} onInvalid={showInvalidField} onChange={clearFieldError} aria-busy={busy && feedbackForm === 'admin-link'}>
            <fieldset disabled={connectionsDisabled} className="min-w-0 space-y-4">
              <label className="block space-y-2 text-sm font-medium">Enlace de Google Maps<input {...fieldProps('admin-link-maps', 'admin-link-maps-help')} name="google_maps_url" required type="url" maxLength={4096} placeholder="https://maps.app.goo.gl/…" className={field} value={url} onChange={(event) => { setUrl(event.target.value); setConfirmed(false); setError(''); setNotice('') }} /></label>
              <FieldError id="admin-link-maps-error" error={fieldErrors['admin-link-maps']} />
              <p className="text-xs leading-5 text-slate-500" id="admin-link-maps-help">Abre la ficha del negocio en Google Maps y usa Compartir → Copiar enlace. Vincular la ficha no consume créditos de SerpApi ni importa reseñas.</p>
              <label className="flex items-start gap-2 text-sm"><input {...fieldProps('admin-link-confirm')} name="confirmed" required type="checkbox" className="mt-1 shrink-0" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />Confirmo que la ficha corresponde a {currentCatalog.tenant.nombre}.</label>
              <FieldError id="admin-link-confirm-error" error={fieldErrors['admin-link-confirm']} />
              <button type="submit" className={primary} disabled={connectionsDisabled || !confirmed}>{busy && feedbackForm === 'admin-link' ? 'Guardando…' : 'Vincular Google Maps'}</button>
            </fieldset>
          </form>
        </>}
        {feedbackForm === 'admin-link' && <div className="mt-3 space-y-2">
          {busy && <p role="status" className="text-sm text-slate-600">Guardando la conexión…</p>}
          <OperationResult error={error} notice={notice} />
        </div>}
        {currentCatalog && <div className="mt-6 border-t border-[#e5e5ea] pt-5"><h4 className="text-sm font-semibold">Cuentas con acceso a este negocio</h4>{currentCatalog.users?.length ? <ul className="mt-3 divide-y divide-[#e5e5ea]">{currentCatalog.users.map((user) => <li key={user.id} className="py-3 text-sm"><p className="font-medium">{user.nombre}</p><p className="break-all text-slate-600">{user.correo}</p><p className="mt-1 text-xs text-slate-500">{user.rol === 'admin_tenant' ? 'Administrador del negocio' : 'Usuario del negocio'} · {user.estado === 'activo' ? 'Cuenta activa' : 'Cuenta inactiva'}</p></li>)}</ul> : <p className="mt-2 text-sm text-slate-500">Todavía no hay cuentas asignadas.</p>}</div>}
      </section>
    </div>
  </section>
}
