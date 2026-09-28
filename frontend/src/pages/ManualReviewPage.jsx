import { useState } from 'react'
import { AlertCircle, ArrowLeft, ClipboardPenLine, Info, Save } from 'lucide-react'
import { Link } from 'react-router-dom'


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

  if (!form.fecha) {
    errors.fecha = 'Selecciona la fecha de la review.'
  }

  if (!form.puntuacion) {
    errors.puntuacion = 'Selecciona una puntuación.'
  } else if (!Number.isInteger(score) || score < 1 || score > 5) {
    errors.puntuacion = 'La puntuación debe ser un valor entre 1 y 5.'
  }

  return errors
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
  const [isFormValid, setIsFormValid] = useState(false)

  function handleChange(event) {
    const { name, value } = event.target

    setForm((currentForm) => ({ ...currentForm, [name]: value }))
    setErrors((currentErrors) => {
      const nextErrors = { ...currentErrors }
      delete nextErrors[name]
      return nextErrors
    })
    setIsFormValid(false)
  }

  function handleSubmit(event) {
    event.preventDefault()

    const nextErrors = validateForm(form)
    setErrors(nextErrors)
    setIsFormValid(Object.keys(nextErrors).length === 0)
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
                  id="autor"
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

            {isFormValid && (
              <div className="flex items-start gap-3 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-800" role="status">
                <Info aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
                <p>
                  Los datos del formulario son válidos. El guardado estará disponible cuando se integre el registro con la API.
                  Esta review todavía no fue registrada.
                </p>
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
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#10233f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200"
                type="submit"
              >
                <Save aria-hidden="true" size={17} />
                Registrar review
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  )
}

export default ManualReviewPage
