import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

import { updateUser } from '../../services/userService.js'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const inputClasses = 'mt-2 block w-full rounded-xl border bg-[#fbfcfe] px-4 py-3 text-sm text-[#10233f] outline-none transition placeholder:text-slate-400 focus:border-[#0f766e] focus:ring-4 focus:ring-teal-100'

function getRequestError(error) {
  if (error.response?.status === 401) {
    return 'Tu sesión no es válida. Inicia sesión nuevamente.'
  }
  if (error.response?.status === 403) {
    return 'No tienes permiso para editar usuarios de esta organización.'
  }
  if (error.response?.status === 404) {
    return 'Este usuario ya no está disponible en tu organización.'
  }
  return 'No fue posible guardar los cambios. Intenta nuevamente.'
}

function EditUserForm({ user, onClose, onUpdated }) {
  const dialogRef = useRef(null)
  const nameInputRef = useRef(null)
  const emailInputRef = useRef(null)
  const submittingRef = useRef(false)
  const [values, setValues] = useState(() => ({ nombre: user.nombre, correo: user.correo }))
  const [errors, setErrors] = useState({})
  const [requestError, setRequestError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (!dialogRef.current.open) {
      dialogRef.current.showModal()
    }
    nameInputRef.current?.focus()
  }, [])

  function handleChange(event) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: undefined }))
    setRequestError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (submittingRef.current) return

    const nombre = values.nombre.trim()
    const correo = values.correo.trim()
    const nextErrors = {}
    if (!nombre) nextErrors.nombre = 'Escribe el nombre de la persona.'
    if (!correo) {
      nextErrors.correo = 'Escribe el correo electrónico.'
    } else if (!emailPattern.test(correo)) {
      nextErrors.correo = 'Escribe un correo electrónico válido.'
    }
    setErrors(nextErrors)
    if (nextErrors.nombre) nameInputRef.current?.focus()
    else if (nextErrors.correo) emailInputRef.current?.focus()
    if (Object.keys(nextErrors).length > 0) return

    const changes = {}
    if (nombre !== user.nombre) changes.nombre = nombre
    if (correo !== user.correo) changes.correo = correo
    if (Object.keys(changes).length === 0) {
      setRequestError('No hay cambios para guardar.')
      return
    }

    submittingRef.current = true
    setIsSubmitting(true)
    setRequestError('')
    try {
      const updatedUser = await updateUser(user.id, changes)
      onUpdated(updatedUser)
      dialogRef.current.close()
    } catch (error) {
      if (error.response?.status === 409) {
        setErrors((current) => ({ ...current, correo: 'Ya existe un usuario con ese correo.' }))
        emailInputRef.current?.focus()
      } else {
        setRequestError(getRequestError(error))
      }
    } finally {
      submittingRef.current = false
      setIsSubmitting(false)
    }
  }

  return (
    <dialog
      aria-labelledby="edit-user-title"
      aria-describedby="edit-user-description"
      className="m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-2xl border border-[#d8e1ec] bg-white p-0 text-[#10233f] shadow-[0_24px_80px_rgba(16,35,63,0.18)] backdrop:bg-[#10233f]/40"
      onCancel={(event) => {
        if (submittingRef.current) event.preventDefault()
      }}
      onClose={onClose}
      ref={dialogRef}
    >
      <div className="border-b border-[#e6edf5] px-6 py-5 sm:px-8 sm:py-6">
        <div className="flex items-start justify-between gap-5">
          <div>
            <p className="text-xs font-semibold tracking-wide text-[#0f766e]">Equipo y acceso</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight" id="edit-user-title">
              Editar usuario
            </h2>
          </div>
          <button
            aria-label="Cerrar formulario"
            className="grid size-9 shrink-0 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-[#10233f] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
            disabled={isSubmitting}
            onClick={() => dialogRef.current.close()}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-600" id="edit-user-description">
          Actualiza los datos de esta persona en tu organización.
        </p>
      </div>

      <form aria-busy={isSubmitting} noValidate onSubmit={handleSubmit}>
        <div className="space-y-5 px-6 py-6 sm:px-8">
          {requestError && (
            <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-800" role="alert">
              {requestError}
            </p>
          )}
          <div>
            <label className="block text-sm font-medium text-[#253a54]" htmlFor="edit-user-name">Nombre</label>
            <input
              aria-describedby={errors.nombre ? 'edit-user-name-error' : undefined}
              aria-invalid={Boolean(errors.nombre)}
              autoComplete="name"
              className={`${inputClasses} ${errors.nombre ? 'border-red-300' : 'border-[#cbd6e3]'}`}
              disabled={isSubmitting}
              id="edit-user-name"
              maxLength={255}
              name="nombre"
              onChange={handleChange}
              ref={nameInputRef}
              required
              type="text"
              value={values.nombre}
            />
            {errors.nombre && <p className="mt-2 text-xs text-red-700" id="edit-user-name-error">{errors.nombre}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-[#253a54]" htmlFor="edit-user-email">Correo electrónico</label>
            <input
              aria-describedby={errors.correo ? 'edit-user-email-error' : undefined}
              aria-invalid={Boolean(errors.correo)}
              autoComplete="email"
              className={`${inputClasses} ${errors.correo ? 'border-red-300' : 'border-[#cbd6e3]'}`}
              disabled={isSubmitting}
              id="edit-user-email"
              maxLength={320}
              name="correo"
              onChange={handleChange}
              ref={emailInputRef}
              required
              type="email"
              value={values.correo}
            />
            {errors.correo && <p className="mt-2 text-xs text-red-700" id="edit-user-email-error">{errors.correo}</p>}
          </div>
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-[#e6edf5] px-6 py-5 sm:flex-row sm:justify-end sm:px-8">
          <button
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#cbd6e3] bg-white px-5 text-sm font-semibold text-[#10233f] transition hover:bg-[#f6f8fb] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
            disabled={isSubmitting}
            onClick={() => dialogRef.current.close()}
            type="button"
          >
            Cancelar
          </button>
          <button
            className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#10233f] px-5 text-sm font-semibold text-white transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-65"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      </form>
    </dialog>
  )
}

export default EditUserForm
