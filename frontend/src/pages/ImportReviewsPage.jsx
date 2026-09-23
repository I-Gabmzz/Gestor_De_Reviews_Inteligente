import { useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, FileUp, Loader2, Table2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { importReviews } from '../services/importService.js'


const allowedExtensions = ['.csv', '.xlsx']

function getErrorMessage(error) {
  if (!error.response) {
    return 'No pudimos conectar con el servidor. Verifica que el backend esté activo.'
  }

  if (error.response.status === 401) {
    return 'Tu sesión expiró o no está disponible. Inicia sesión nuevamente.'
  }

  if (error.response.status === 403) {
    return 'Tu usuario no tiene un tenant de negocio asignado para importar reviews.'
  }

  return error.response.data?.detail || 'No fue posible importar el archivo. Revisa el formato e inténtalo nuevamente.'
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
        <div>
          <h2 className="font-semibold">El archivo necesita correcciones</h2>
          <p className="mt-1 text-sm leading-6 text-amber-800">
            Se encontraron {result.total_errores} errores. Corrige el archivo y vuelve a importarlo.
          </p>

          {result.errores_globales?.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
              {result.errores_globales.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}

          {result.errores_por_fila?.length > 0 && (
            <div className="mt-4 overflow-hidden rounded-lg border border-amber-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="bg-amber-100/70 text-xs uppercase text-amber-900">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Fila</th>
                    <th className="px-3 py-2 font-semibold">Campo</th>
                    <th className="px-3 py-2 font-semibold">Error</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-amber-100">
                  {result.errores_por_fila.slice(0, 6).map((rowError) => (
                    <tr key={`${rowError.fila}-${rowError.campo}-${rowError.mensaje}`}>
                      <td className="px-3 py-2">{rowError.fila}</td>
                      <td className="px-3 py-2">{rowError.campo}</td>
                      <td className="px-3 py-2">{rowError.mensaje}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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

  function handleFileChange(event) {
    setFile(event.target.files?.[0] ?? null)
    setErrorMessage('')
    setResult(null)
  }

  async function handleSubmit(event) {
    event.preventDefault()

    if (!file || status === 'loading') {
      return
    }

    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!allowedExtensions.includes(extension)) {
      setErrorMessage('Selecciona un archivo CSV o Excel con extensión .csv o .xlsx.')
      setResult(null)
      return
    }

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
    }
  }

  const isLoading = status === 'loading'

  return (
    <main className="min-h-screen bg-[#eef2f7] px-5 py-6 text-[#10233f] sm:px-8 lg:px-10">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <header className="rounded-lg border border-[#d8e1ec] bg-white px-5 py-5 shadow-[0_14px_36px_rgba(16,35,63,0.07)] sm:px-6">
          <Link className="inline-flex items-center gap-2 text-sm font-semibold text-[#0f766e]" to="/dashboard">
            <ArrowLeft aria-hidden="true" size={16} />
            Volver al dashboard
          </Link>
          <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm font-medium text-[#0f766e]">Importación de reviews</p>
              <h1 className="mt-1 text-2xl font-semibold text-[#10233f] sm:text-3xl">Cargar CSV o Excel</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Las reviews válidas se guardan en el tenant de tu sesión y quedan disponibles para consulta y dashboard.
              </p>
            </div>
            <Link
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#cbd6e3] bg-white px-4 py-2.5 text-sm font-semibold text-[#10233f] transition hover:bg-[#f6f8fb] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
              to="/reviews"
            >
              <Table2 aria-hidden="true" size={16} />
              Ver reviews
            </Link>
          </div>
        </header>

        <section className="rounded-lg border border-[#d8e1ec] bg-white p-5 shadow-[0_14px_36px_rgba(16,35,63,0.07)] sm:p-6">
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-[#253a54]" htmlFor="reviews-file">
                Archivo de reviews
              </label>
              <input
                accept=".csv,.xlsx"
                className="block w-full rounded-lg border border-[#cbd6e3] bg-[#fbfcfe] px-4 py-3 text-sm text-[#10233f] file:mr-4 file:rounded-lg file:border-0 file:bg-[#10233f] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white focus:border-[#0f766e] focus:outline-none focus:ring-4 focus:ring-teal-100"
                disabled={isLoading}
                id="reviews-file"
                onChange={handleFileChange}
                type="file"
              />
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Encabezados requeridos: contenido, fecha y puntuacion. También puedes incluir autor y fuente.
              </p>
            </div>

            {errorMessage && (
              <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
                <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
                {errorMessage}
              </div>
            )}

            <button
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#10233f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!file || isLoading}
              type="submit"
            >
              {isLoading ? <Loader2 aria-hidden="true" className="animate-spin" size={17} /> : <FileUp aria-hidden="true" size={17} />}
              {isLoading ? 'Importando…' : 'Importar reviews'}
            </button>
          </form>
        </section>

        <ValidationSummary result={result} />

        {status === 'success' && (
          <section className="flex flex-col gap-3 rounded-lg border border-[#d8e1ec] bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">
              Las métricas se recalcularán al abrir el dashboard y el listado consultará la base actualizada.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Link className="inline-flex items-center justify-center rounded-lg bg-[#10233f] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#19365c]" to="/dashboard">
                Ver dashboard
              </Link>
              <Link className="inline-flex items-center justify-center rounded-lg border border-[#cbd6e3] px-4 py-2.5 text-sm font-semibold text-[#10233f] transition hover:bg-[#f6f8fb]" to="/reviews">
                Ver todas las reviews
              </Link>
            </div>
          </section>
        )}
      </div>
    </main>
  )
}

export default ImportReviewsPage
