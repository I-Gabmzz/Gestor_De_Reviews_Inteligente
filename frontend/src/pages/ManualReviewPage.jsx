import { useRef, useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, ClipboardPenLine, Loader2, Save } from 'lucide-react'
import { Link } from 'react-router-dom'

import { createReview } from '../services/reviewService.js'


const initialForm = {
  autor: '',
  contenido: '',
  fecha: '',
  puntuacion: '',
}

function validateForm(form) {
  const errors = {}
  const score = Number(form.puntuacion)

  if (!form.contenido.trim()) {
    errors.contenido = 'Escribe el contenido de la review.'
  }

  if (!form.fecha || Number.isNaN(new Date(`${form.fecha}T00:00:00`).getTime())) {
    errors.fecha = 'Selecciona la fecha de la review.'
  }

  if (!form.puntuacion) {
    errors.puntuacion = 'Selecciona una puntuación.'
  } else if (!Number.isInteger(score) || score < 1 || score > 5) {
    errors.puntuacion = 'La puntuación debe ser un valor entre 1 y 5.'
  }

  return errors
}

function getSaveError(error) {
  if (error.code === 'UNEXPECTED_CREATE_RESPONSE') {
    return 'No se pudo confirmar el registro. Consulta el listado antes de intentar enviarla de nuevo.'
  }
  if (!error.response) {
    return 'No pudimos conectar con el servidor. Tus datos siguen en el formulario; inténtalo nuevamente.'
  }
  if (error.response.status === 401) {
    return 'Tu sesión expiró. Inicia sesión nuevamente para registrar la review.'
  }
  if (error.response.status === 403) {
    return 'Tu usuario no tiene un tenant de negocio asignado para registrar reviews.'
  }
  if (error.response.status === 422) {
    return 'Revisa los datos indicados antes de registrar la review.'
  }
  return 'No fue posible registrar la review. Tus datos siguen en el formulario; inténtalo nuevamente.'
}

function RequiredMark() {
  return (
    <span aria-hidden="true" className="ml-1 text-red-600">
      *
    </span>
  )
}

function ManualReviewPage() {
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [saveError, setSaveError] = useState('')
  const [status, setStatus] = useState('idle')
  const isSavingRef = useRef(false)
  const isSaving = status === 'saving'

  function handleChange(event) {
    const { name, value } = event.target

    setForm((currentForm) => ({ ...currentForm, [name]: value }))
    setErrors((currentErrors) => {
      const nextErrors = { ...currentErrors }
      delete nextErrors[name]
      return nextErrors
    })
    setSaveError('')
    setStatus('idle')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (isSavingRef.current) return

    const nextErrors = validateForm(form)
    setErrors(nextErrors)
    setSaveError('')
    setStatus('idle')
    if (Object.keys(nextErrors).length > 0) return

    const payload = {
      autor: form.autor.trim() || null,
      contenido: form.contenido.trim(),
      fecha: `${form.fecha}T00:00:00`,
      puntuacion: Number(form.puntuacion),
    }

    isSavingRef.current = true
    setStatus('saving')
    try {
      await createReview(payload)
      setForm(initialForm)
      setStatus('success')
    } catch (error) {
      setSaveError(getSaveError(error))
      setStatus('idle')
      if (error.response?.status === 422 && Array.isArray(error.response.data?.detail)) {
        const serverErrors = {}
        for (const item of error.response.data.detail) {
          const field = item.loc?.[1]
          if (Object.hasOwn(initialForm, field)) {
            serverErrors[field] = field === 'puntuacion'
              ? 'La puntuación debe ser un valor entre 1 y 5.'
              : `Revisa el campo ${field}.`
          }
        }
        setErrors(serverErrors)
      }
    } finally {
      isSavingRef.current = false
    }
  }

  const fieldClassName = (hasError) => (
    `w-full rounded-lg border bg-[#fbfcfe] px-4 py-3 text-sm text-[#10233f] outline-none transition placeholder:text-slate-400 focus:ring-4 ${
      hasError
        ? 'border-red-300 focus:border-red-500 focus:ring-red-100'
        : 'border-[#cbd6e3] focus:border-[#0f766e] focus:ring-teal-100'
    }`
  )

  return (
    <main className="min-h-screen bg-[#eef2f7] px-5 py-6 text-[#10233f] sm:px-8 lg:px-10">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <header className="rounded-lg border border-[#d8e1ec] bg-white px-5 py-5 shadow-[0_14px_36px_rgba(16,35,63,0.07)] sm:px-6">
          <Link className="inline-flex items-center gap-2 text-sm font-semibold text-[#0f766e]" to="/reviews">
            <ArrowLeft aria-hidden="true" size={16} />
            Volver a reviews
          </Link>

          <div className="mt-5 flex items-start gap-4">
            <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-[#10233f] text-teal-200">
              <ClipboardPenLine aria-hidden="true" size={22} />
            </span>
            <div>
              <p className="text-sm font-medium text-[#0f766e]">Registro manual</p>
              <h1 className="mt-1 text-2xl font-semibold text-[#10233f] sm:text-3xl">Nueva review</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Captura los datos proporcionados por el cliente. Los campos marcados con asterisco son obligatorios.
              </p>
            </div>
          </div>
        </header>

        <section className="rounded-lg border border-[#d8e1ec] bg-white p-5 shadow-[0_14px_36px_rgba(16,35,63,0.07)] sm:p-6">
          <form className="space-y-6" noValidate onSubmit={handleSubmit}>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-[#253a54]" htmlFor="autor">
                  Autor <span className="font-normal text-slate-500">(opcional)</span>
                </label>
                <input
                  className={fieldClassName(false)}
                  disabled={isSaving}
                  id="autor"
                  maxLength={255}
                  name="autor"
                  onChange={handleChange}
                  placeholder="Nombre del cliente"
                  type="text"
                  value={form.autor}
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-[#253a54]" htmlFor="fecha">
                  Fecha <RequiredMark />
                </label>
                <input
                  aria-describedby={errors.fecha ? 'fecha-error' : undefined}
                  aria-invalid={Boolean(errors.fecha)}
                  className={fieldClassName(Boolean(errors.fecha))}
                  disabled={isSaving}
                  id="fecha"
                  name="fecha"
                  onChange={handleChange}
                  required
                  type="date"
                  value={form.fecha}
                />
                {errors.fecha && (
                  <p className="mt-2 text-sm text-red-700" id="fecha-error" role="alert">
                    {errors.fecha}
                  </p>
                )}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-[#253a54]" htmlFor="contenido">
                Contenido <RequiredMark />
              </label>
              <textarea
                aria-describedby={errors.contenido ? 'contenido-error contenido-help' : 'contenido-help'}
                aria-invalid={Boolean(errors.contenido)}
                className={`${fieldClassName(Boolean(errors.contenido))} min-h-36 resize-y`}
                disabled={isSaving}
                id="contenido"
                name="contenido"
                onChange={handleChange}
                placeholder="Escribe el comentario del cliente"
                required
                value={form.contenido}
              />
              <p className="mt-2 text-xs text-slate-500" id="contenido-help">
                Registra el comentario tal como fue expresado por el cliente.
              </p>
              {errors.contenido && (
                <p className="mt-2 text-sm text-red-700" id="contenido-error" role="alert">
                  {errors.contenido}
                </p>
              )}
            </div>

            <div className="max-w-xs">
              <label className="mb-2 block text-sm font-medium text-[#253a54]" htmlFor="puntuacion">
                Puntuación <RequiredMark />
              </label>
              <select
                aria-describedby={errors.puntuacion ? 'puntuacion-error' : 'puntuacion-help'}
                aria-invalid={Boolean(errors.puntuacion)}
                className={fieldClassName(Boolean(errors.puntuacion))}
                disabled={isSaving}
                id="puntuacion"
                name="puntuacion"
                onChange={handleChange}
                required
                value={form.puntuacion}
              >
                <option value="">Selecciona una puntuación</option>
                {[1, 2, 3, 4, 5].map((score) => (
                  <option key={score} value={score}>
                    {score} {score === 1 ? 'estrella' : 'estrellas'}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-slate-500" id="puntuacion-help">
                Usa una escala de 1 a 5 estrellas.
              </p>
              {errors.puntuacion && (
                <p className="mt-2 text-sm text-red-700" id="puntuacion-error" role="alert">
                  {errors.puntuacion}
                </p>
              )}
            </div>

            {Object.keys(errors).length > 0 && (
              <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
                <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
                Revisa los campos obligatorios antes de continuar.
              </div>
            )}

            {saveError && (
              <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
                <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
                {saveError}
              </div>
            )}

            {status === 'success' && (
              <div className="flex flex-col gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800 sm:flex-row sm:items-center sm:justify-between" role="status">
                <div className="flex items-start gap-3">
                  <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
                  <span>La review se registró correctamente.</span>
                </div>
                <Link className="font-semibold underline underline-offset-4" to="/reviews">
                  Ver reviews
                </Link>
              </div>
            )}

            <div className="flex flex-col-reverse gap-3 border-t border-[#e6edf5] pt-5 sm:flex-row sm:items-center sm:justify-end">
              <Link
                className="inline-flex items-center justify-center rounded-lg border border-[#cbd6e3] bg-white px-4 py-3 text-sm font-semibold text-[#10233f] transition hover:bg-[#f6f8fb] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
                to="/reviews"
              >
                Cancelar
              </Link>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#10233f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isSaving}
                type="submit"
              >
                {isSaving ? <Loader2 aria-hidden="true" className="animate-spin" size={17} /> : <Save aria-hidden="true" size={17} />}
                {isSaving ? 'Registrando…' : 'Registrar review'}
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  )
}

export default ManualReviewPage
