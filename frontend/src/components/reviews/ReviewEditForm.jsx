import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Loader2, Save, X } from 'lucide-react'

import { updateReview } from '../../api/reviews.js'


const fieldMessages = {
  autor: 'El autor puede tener hasta 255 caracteres.',
  contenido: 'Escribe el contenido de la review.',
  fecha: 'Selecciona una fecha y hora válidas.',
  fuente: 'Escribe una fuente de hasta 100 caracteres.',
  puntuacion: 'La puntuación debe ser un número entero entre 1 y 5.',
}

function validate(values) {
  const errors = {}
  if (values.autor.trim().length > 255) errors.autor = fieldMessages.autor
  if (!values.contenido.trim()) errors.contenido = fieldMessages.contenido
  if (!values.fecha || Number.isNaN(new Date(values.fecha).getTime())) errors.fecha = fieldMessages.fecha
  if (!values.fuente.trim() || values.fuente.trim().length > 100) errors.fuente = fieldMessages.fuente
  const score = Number(values.puntuacion)
  if (!values.puntuacion || !Number.isInteger(score) || score < 1 || score > 5) {
    errors.puntuacion = fieldMessages.puntuacion
  }
  return errors
}

function getSaveError(error) {
  if (!error.response) return 'No pudimos conectar con el servidor. Tus cambios siguen en el formulario; intenta guardarlos nuevamente.'
  if (error.response.status === 401) return 'Tu sesión expiró. Inicia sesión nuevamente para guardar los cambios.'
  if (error.response.status === 403) return 'No tienes permiso para editar esta review.'
  if (error.response.status === 404) return 'Esta review ya no está disponible. Cancela la edición y actualiza el listado.'
  if (error.response.status === 422) return 'Revisa los datos indicados antes de guardar.'
  return 'No fue posible guardar los cambios. Intenta nuevamente.'
}

function FieldError({ name, errors }) {
  return errors[name] ? (
    <p className="mt-1.5 text-sm text-red-700" id={`review-edit-${name}-error`}>{errors[name]}</p>
  ) : null
}

function ReviewEditForm({ review, onCancel, onSaved }) {
  const dialogRef = useRef(null)
  const formRef = useRef(null)
  const [initialValues] = useState(() => ({
    autor: review.autor ?? '',
    contenido: review.contenido,
    fecha: review.fecha.slice(0, 19),
    fuente: review.fuente,
    puntuacion: String(review.puntuacion),
  }))
  const [values, setValues] = useState(initialValues)
  const [errors, setErrors] = useState({})
  const [errorMessage, setErrorMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const isSavingRef = useRef(false)

  useEffect(() => {
    const dialog = dialogRef.current
    dialog.showModal()
    return () => dialog.close()
  }, [])

  function handleChange(event) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: undefined }))
    setErrorMessage('')
  }

  function focusError(nextErrors) {
    formRef.current?.elements.namedItem(Object.keys(nextErrors)[0])?.focus()
  }

  function close() {
    if (isSavingRef.current) return
    dialogRef.current.close()
    onCancel()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (isSavingRef.current) return

    const nextErrors = validate(values)
    setErrors(nextErrors)
    setErrorMessage('')
    if (Object.keys(nextErrors).length > 0) {
      focusError(nextErrors)
      return
    }

    const normalizedValues = {
      autor: values.autor.trim() || null,
      contenido: values.contenido.trim(),
      fecha: values.fecha,
      fuente: values.fuente.trim(),
      puntuacion: Number(values.puntuacion),
    }
    const changes = {}
    for (const [field, value] of Object.entries(normalizedValues)) {
      const originalValue = field === 'fecha' ? initialValues.fecha : review[field]
      if (value !== originalValue) changes[field] = value
    }

    if (Object.keys(changes).length === 0) {
      setErrorMessage('No has modificado ningún campo. Puedes cancelar para volver al detalle.')
      return
    }

    isSavingRef.current = true
    setIsSaving(true)
    try {
      const updatedReview = await updateReview(review.id, changes)
      dialogRef.current.close()
      onSaved(updatedReview)
    } catch (error) {
      setErrorMessage(getSaveError(error))
      if (error.response?.status === 422) {
        const detail = error.response.data?.detail
        const serverErrors = {}
        if (Array.isArray(detail)) {
          for (const item of detail) {
            const field = item.loc?.[1]
            if (Object.hasOwn(fieldMessages, field)) serverErrors[field] = fieldMessages[field]
          }
        }
        setErrors(serverErrors)
        focusError(serverErrors)
      }
    } finally {
      isSavingRef.current = false
      setIsSaving(false)
    }
  }

  function inputProps(name) {
    return {
      'aria-describedby': errors[name] ? `review-edit-${name}-error` : undefined,
      'aria-invalid': Boolean(errors[name]),
      className: `w-full rounded-lg border bg-white px-3 py-2.5 text-base text-slate-900 outline-none transition focus:ring-4 disabled:bg-slate-50 ${errors[name] ? 'border-red-400 focus:border-red-500 focus:ring-red-100' : 'border-slate-300 focus:border-sky-500 focus:ring-sky-100'}`,
      disabled: isSaving,
      id: `review-edit-${name}`,
      name,
      onChange: handleChange,
      value: values[name],
    }
  }

  return (
    <dialog
      aria-labelledby="review-edit-title"
      className="fixed inset-0 m-auto max-h-[calc(100dvh_-_2rem)] w-[calc(100%_-_2rem)] max-w-xl overflow-y-auto rounded-xl border border-slate-200 bg-white p-0 text-slate-900 shadow-xl backdrop:bg-slate-900/40"
      onCancel={(event) => { event.preventDefault(); close() }}
      ref={dialogRef}
    >
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-6">
        <div>
          <h2 className="text-xl font-semibold" id="review-edit-title">Editar review</h2>
          <p className="mt-1 text-sm text-slate-500">Corrige o complementa los datos de este comentario.</p>
        </div>
        <button
          aria-label="Cerrar edición"
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-100 disabled:opacity-50"
          disabled={isSaving}
          onClick={close}
          type="button"
        >
          <X aria-hidden="true" size={20} />
        </button>
      </div>

      <form className="space-y-5 px-5 py-5 sm:px-6" noValidate onSubmit={handleSubmit} ref={formRef}>
        {errorMessage && (
          <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
            <p>{errorMessage}</p>
          </div>
        )}

        <div>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="review-edit-autor">Autor <span className="font-normal text-slate-500">(opcional)</span></label>
          <input {...inputProps('autor')} maxLength={255} type="text" />
          <FieldError errors={errors} name="autor" />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="review-edit-contenido">Contenido</label>
          <textarea {...inputProps('contenido')} required rows={4} />
          <FieldError errors={errors} name="contenido" />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="review-edit-fecha">Fecha y hora</label>
          <input {...inputProps('fecha')} required step="1" type="datetime-local" />
          <FieldError errors={errors} name="fecha" />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-sm font-medium" htmlFor="review-edit-fuente">Fuente</label>
            <input {...inputProps('fuente')} maxLength={100} required type="text" />
            <FieldError errors={errors} name="fuente" />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium" htmlFor="review-edit-puntuacion">Puntuación (1–5)</label>
            <input {...inputProps('puntuacion')} max={5} min={1} required step="1" type="number" />
            <FieldError errors={errors} name="puntuacion" />
          </div>
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:justify-end">
          <button
            className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-100 disabled:opacity-60"
            disabled={isSaving}
            onClick={close}
            type="button"
          >Cancelar</button>
          <button
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSaving}
            type="submit"
          >
            {isSaving ? <Loader2 aria-hidden="true" className="animate-spin" size={16} /> : <Save aria-hidden="true" size={16} />}
            {isSaving ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      </form>
    </dialog>
  )
}

export default ReviewEditForm
