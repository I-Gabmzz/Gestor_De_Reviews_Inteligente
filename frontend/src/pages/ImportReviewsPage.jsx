import { useRef, useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, FileUp, Loader2, Table2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { importReviews } from '../services/importService.js'
import ExternalReviewImport from '../components/ExternalReviewImport.jsx'


const allowedExtensions = ['.csv', '.xlsx']

function getErrorMessage(error) {
  if (!error.response) {
    return 'No pudimos conectar con el servidor. Verifica que el backend esté activo.'
  }

  if (error.response.status === 401) {
    return 'Tu sesión expiró o no está disponible. Inicia sesión nuevamente.'
  }

  if (error.response.status === 403) {
    return 'No tienes permiso para importar reviews. Si tu acceso cambió, vuelve a iniciar sesión.'
  }

  const detail = error.response.data?.detail
  return typeof detail === 'string' && detail ? detail : 'No fue posible importar el archivo. Revisa el formato e inténtalo nuevamente.'
}

function ValidationSummary({ result }) {
  if (!result) {
    return null
  }

  if (result.es_valido) {
    return (
      <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5 text-emerald-800" role="status">
        <div className="flex gap-3">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={21} />
          <div>
            <h2 className="font-semibold">Importación completada</h2>
            <p className="mt-1 text-sm leading-6 text-emerald-700">
              Se guardaron {result.filas_guardadas} de {result.total_filas} filas válidas en la base de datos.
            </p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-amber-900" role="alert">
      <div className="flex gap-3">
        <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={21} />
        <div className="min-w-0 flex-1 wrap-anywhere">
          <h2 className="font-semibold">El archivo necesita correcciones</h2>
          <p className="mt-1 text-sm leading-6 text-amber-800">
            {result.total_errores === 1 ? 'Se encontró 1 error.' : `Se encontraron ${result.total_errores} errores.`} Corrige el archivo y vuelve a importarlo.
          </p>

          {result.errores_globales?.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
              {result.errores_globales.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}

          {result.errores_por_fila?.length > 0 && (
            <ul aria-label="Errores por fila" className="mt-4 divide-y divide-amber-100 rounded-lg border border-amber-200 bg-white text-sm">
              {result.errores_por_fila.slice(0, 6).map((rowError) => (
                <li className="p-3" key={`${rowError.fila}-${rowError.campo}-${rowError.mensaje}`}>
                  <p className="font-semibold">Fila {rowError.fila} · {rowError.campo}</p>
                  <p className="mt-1">{rowError.mensaje}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}

function ImportReviewsPage() {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [result, setResult] = useState(null)
  const pending = useRef(false)
  const extension = file?.name.match(/\.[^.]+$/)?.[0].toLowerCase()
  const invalidExtension = Boolean(file && !allowedExtensions.includes(extension))
  const fileError = invalidExtension ? 'Selecciona un archivo CSV o Excel con extensión .csv o .xlsx.'
    : result?.es_valido === false ? 'Corrige los errores del archivo y vuelve a seleccionarlo.' : ''

  function handleFileChange(event) {
    setFile(event.target.files?.[0] ?? null)
    setStatus('idle')
    setErrorMessage('')
    setResult(null)
  }

  async function handleSubmit(event) {
    event.preventDefault()

    if (!file || invalidExtension || pending.current) {
      return
    }

    pending.current = true
    setStatus('loading')
    setErrorMessage('')
    setResult(null)

    try {
      const importResult = await importReviews(file)
      setResult(importResult)
      setStatus(importResult.es_valido ? 'success' : 'ready')
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
      setStatus('error')
    } finally {
      pending.current = false
    }
  }

  const isLoading = status === 'loading'

  return (
    <main className="focus-controls min-h-screen bg-[#f5f5f7] px-5 py-6 text-[#1d1d1f] sm:px-8 lg:px-10">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <header className="rounded-lg border border-[#e5e5ea] bg-white px-5 py-5 shadow-[0_14px_36px_rgba(0,0,0,0.07)] sm:px-6">
          <Link className="inline-flex items-center gap-2 text-sm font-semibold text-[#515154]" to="/dashboard">
            <ArrowLeft aria-hidden="true" size={16} />
            Volver al dashboard
          </Link>
          <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm font-medium text-[#515154]">Importación de reviews</p>
              <h1 className="mt-1 text-2xl font-semibold text-[#1d1d1f] sm:text-3xl">Importar reviews</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Las reviews válidas se guardan en el tenant de tu sesión y quedan disponibles para consulta y dashboard.
              </p>
            </div>
            <Link
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm font-semibold text-[#1d1d1f] transition hover:bg-[#f5f5f7] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
              to="/reviews"
            >
              <Table2 aria-hidden="true" size={16} />
              Ver reviews
            </Link>
          </div>
        </header>

        <section className="rounded-lg border border-[#e5e5ea] bg-white p-5 shadow-[0_14px_36px_rgba(0,0,0,0.07)] sm:p-6">
          <h2 className="mb-5 text-xl font-semibold">Cargar CSV o Excel</h2>
          <form aria-busy={isLoading} className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-[#424245]" htmlFor="reviews-file">
                Archivo de reviews
              </label>
              <input
                accept=".csv,.xlsx"
                aria-describedby={fileError ? 'reviews-file-help reviews-file-error' : 'reviews-file-help'}
                aria-invalid={fileError ? true : undefined}
                className="block w-full min-w-0 max-w-full file:min-h-11"
                disabled={isLoading}
                id="reviews-file"
                onChange={handleFileChange}
                type="file"
              />
              <p className="mt-2 text-xs leading-5 text-slate-500" id="reviews-file-help">
                Encabezados requeridos: contenido, fecha y puntuacion. También puedes incluir autor y fuente.
              </p>
              {fileError && <p className="mt-2 text-sm text-red-800" id="reviews-file-error" role={invalidExtension ? 'alert' : undefined}>{fileError}</p>}
            </div>

            {errorMessage && (
              <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
                <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
                {errorMessage}
              </div>
            )}

            <button
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1d1d1f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#333336] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              disabled={!file || invalidExtension || isLoading}
              type="submit"
            >
              {isLoading ? <Loader2 aria-hidden="true" className="motion-safe:animate-spin" size={17} /> : <FileUp aria-hidden="true" size={17} />}
              {isLoading ? 'Importando…' : 'Importar reviews'}
            </button>
          </form>
          {isLoading && <p className="mt-3 text-sm text-slate-600" role="status">Procesando el archivo de reviews…</p>}
        </section>

        <ValidationSummary result={result} />

        {status === 'success' && (
          <section className="flex flex-col gap-3 rounded-lg border border-[#e5e5ea] bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">
              Las métricas se recalcularán al abrir el dashboard y el listado consultará la base actualizada.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Link className="inline-flex items-center justify-center rounded-lg bg-[#1d1d1f] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#333336]" to="/dashboard">
                Ver dashboard
              </Link>
              <Link className="inline-flex items-center justify-center rounded-lg border border-[#d2d2d7] px-4 py-2.5 text-sm font-semibold text-[#1d1d1f] transition hover:bg-[#f5f5f7]" to="/reviews">
                Ver todas las reviews
              </Link>
            </div>
          </section>
        )}
        <ExternalReviewImport />
      </div>
    </main>
  )
}

export default ImportReviewsPage
