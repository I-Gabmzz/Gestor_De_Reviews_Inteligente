import { AlertCircle, CheckCircle2, Download, Loader2, RefreshCw, Table2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import useExternalReviewImport from '../hooks/useExternalReviewImport.js'

const counters = [
  ['input_count', 'Obtenidas'], ['inserted', 'Insertadas'], ['repeated', 'Repetidas'],
  ['changed', 'Cambiadas'], ['omitted', 'Omitidas'], ['rejected', 'Rechazadas'],
]

function ExternalReviewImport() {
  const state = useExternalReviewImport()
  const { data, operation, importing, safety } = state
  const options = data?.connections ?? []
  const selected = options.find((row) => row.business_data_id === state.selected)
  const locked = !importing && (safety.blocked || operation?.requiresReview)
  const disabled = !state.authorized || state.loading || importing || !data?.import_enabled
    || selected?.status !== 'available' || safety.blocked || Boolean(operation?.requiresReview)

  return (
    <section aria-labelledby="external-import-title" className="rounded-lg border border-[#e5e5ea] bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-[#1d1d1f]" id="external-import-title">Importar desde Google</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Selecciona un establecimiento configurado para tu negocio. La importación es manual y consume el presupuesto autorizado.
          </p>
        </div>
        <button className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#d2d2d7] px-3 py-2 text-sm font-semibold text-[#424245] hover:bg-[#f5f5f7] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={!state.authorized || state.loading || importing} onClick={state.refresh} type="button">
          <RefreshCw aria-hidden="true" size={16} />Actualizar conexiones
        </button>
      </div>

      {!state.authorized && <p className="mt-5 text-sm text-red-800" role="alert">Tu sesión no permite importar reseñas externas. Inicia sesión con una cuenta de negocio autorizada.</p>}
      {state.loading && <p className="mt-5 text-sm text-slate-600" role="status">Consultando conexiones de tu negocio…</p>}
      {state.error && <p className="mt-5 text-sm leading-6 text-red-800" role="alert">{state.error}</p>}
      {data && !data.import_enabled && (
        <p className="mt-5 rounded-lg bg-slate-100 p-4 text-sm leading-6 text-slate-700" role="status">
          La importación externa está deshabilitada en el servidor. No puedes habilitarla desde esta página.
        </p>
      )}
      {data && options.length === 0 && (
        <p className="mt-5 text-sm leading-6 text-slate-600" role="status">
          Tu negocio no tiene conexiones externas configuradas. Consulta al responsable; no se pueden crear conexiones desde esta página.
        </p>
      )}
      {data && options.length > 0 && (
        <form aria-busy={importing} className="mt-6 space-y-4" onSubmit={state.submit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-[#424245]" htmlFor="external-establishment">Establecimiento de Google</label>
            <select aria-describedby="external-establishment-help" className="min-h-12 w-full min-w-0 rounded-lg border border-[#d2d2d7] bg-[#fafafa] px-3 py-3 text-sm text-[#1d1d1f] focus:border-[#515154] focus:outline-none focus:ring-4 focus:ring-teal-100 disabled:opacity-60"
              disabled={importing || state.loading} id="external-establishment" onChange={(event) => state.select(event.target.value)} value={state.selected}>
              <option value="">Selecciona un establecimiento</option>
              {options.map((row, index) => <option disabled={row.status !== 'available'} key={row.business_data_id} value={row.business_data_id}>{row.business_name}{options.filter((option) => option.business_name === row.business_name).length > 1 ? ` — Conexión ${index + 1}` : ''}{row.status === 'disabled' ? ' — No disponible' : ''}</option>)}
            </select>
            <p className="mt-2 text-xs leading-5 text-slate-600" id="external-establishment-help">Selecciona la conexión de tu negocio para importar sus reseñas de Google.</p>
          </div>
          {!options.some((row) => row.status === 'available') && <p className="text-sm text-slate-600" role="status">No hay conexiones habilitadas para importar. Consulta al responsable de tu negocio.</p>}
          <button className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#1d1d1f] px-4 py-3 text-sm font-semibold text-white hover:bg-[#333336] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={disabled} type="submit">
            {importing ? <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" size={17} /> : <Download aria-hidden="true" size={17} />}
            {importing ? 'Importando desde Google…' : 'Importar desde Google'}
          </button>
        </form>
      )}
      {importing && <p className="mt-4 text-sm leading-6 text-slate-600" role="status">La consulta puede tardar varios minutos. No envíes otra importación. Salir de la página no cancela el trabajo del servidor.</p>}

      {operation?.kind === 'success' && (
        <div className="mt-6 border-t border-[#e5e5ea] pt-5" role="status">
          <h3 className="flex items-center gap-2 font-semibold text-emerald-800"><CheckCircle2 aria-hidden="true" size={19} />Importación confirmada</h3>
          <dl className="mt-4 grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-3">
            {counters.map(([field, label]) => <div key={field}><dt className="text-sm text-slate-600">{label}</dt><dd className="mt-1 text-xl font-semibold tabular-nums text-[#1d1d1f]">{operation.result[field]}</dd></div>)}
          </dl>
          <p className="mt-4 text-xs leading-5 text-slate-600">Las reseñas cambiadas se informan sin reemplazar los valores locales. Obtenidas corresponde a los registros recibidos, no al total público del establecimiento.</p>
        </div>
      )}
      {operation?.kind === 'error' && <p className="mt-5 flex items-start gap-2 text-sm leading-6 text-red-800" role="alert"><AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />{operation.message}</p>}
      {operation?.kind === 'success' && operation.result.limited && <p className="mt-3 text-sm leading-6 text-amber-900">Se guardó un lote limitado por la configuración del servidor. No representa todas las reseñas del establecimiento.</p>}
      {operation?.kind !== 'success' && operation?.incomplete && <p className="mt-3 text-sm text-amber-900">La adquisición está incompleta.</p>}
      {operation?.kind !== 'success' && operation?.limited && <p className="mt-3 text-sm text-amber-900">La adquisición alcanzó un límite configurado.</p>}
      {operation?.kind === 'error' && operation.obtained !== null && operation.obtained !== undefined && <p className="mt-3 text-sm text-slate-600">Registros obtenidos informados: {operation.obtained}.</p>}
      {locked && <p className="mt-4 rounded-lg bg-amber-50 p-4 text-sm leading-6 text-amber-900" role="status">
        {safety.unavailable || operation?.notSent ? 'El navegador no permite conservar la protección de la operación. No se enviará una importación.' : 'Esta conexión está protegida en esta pestaña. Puede existir una operación pendiente o requerir reconciliación. Consulta las reviews y solicita revisión al responsable antes de continuar. Actualizar las conexiones no desbloquea el envío.'}
      </p>}
      {(operation?.kind === 'success' || locked) && <Link className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#d2d2d7] px-4 py-2.5 text-sm font-semibold text-[#1d1d1f] hover:bg-[#f5f5f7] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100" to="/reviews"><Table2 aria-hidden="true" size={16} />Consultar reviews</Link>}
    </section>
  )
}

export default ExternalReviewImport
