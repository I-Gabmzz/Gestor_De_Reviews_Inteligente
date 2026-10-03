import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

import { createUser } from '../../services/userService.js'

const initialValues = { nombre: '', correo: '', password: '' }
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const inputClasses = 'mt-2 block w-full rounded-xl border bg-[#fbfcfe] px-4 py-3 text-sm text-[#10233f] outline-none transition placeholder:text-slate-400 focus:border-[#0f766e] focus:ring-4 focus:ring-teal-100'

function validate(values) {
  const errors = {}

  if (!values.nombre.trim()) {
    errors.nombre = 'Escribe el nombre de la persona.'
  }

  if (!values.correo.trim()) {
    errors.correo = 'Escribe el correo electrónico.'
  } else if (!emailPattern.test(values.correo.trim())) {
    errors.correo = 'Escribe un correo electrónico válido.'
  }

  if (!values.password) {
    errors.password = 'Escribe una contraseña inicial.'
  }

  return errors
}

function getRequestError(error) {
  if (error.response?.status === 401) {
    return 'Tu sesión no es válida. Inicia sesión nuevamente.'
  }
  if (error.response?.status === 403) {
    return 'No tienes permiso para crear usuarios en esta organización.'
  }
  return 'No fue posible crear el usuario. Intenta nuevamente.'
}

function CreateUserForm({ onClose, onCreated }) {
  const dialogRef = useRef(null)
  const nameInputRef = useRef(null)
  const emailInputRef = useRef(null)
  const passwordInputRef = useRef(null)
  const submittingRef = useRef(false)
  const [values, setValues] = useState(initialValues)
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
    if (submittingRef.current) {
      return
    }

    const nextErrors = validate(values)
    setErrors(nextErrors)
    if (nextErrors.nombre) {
      nameInputRef.current?.focus()
    } else if (nextErrors.correo) {
      emailInputRef.current?.focus()
    } else if (nextErrors.password) {
      passwordInputRef.current?.focus()
    }
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    submittingRef.current = true
    setIsSubmitting(true)
    setRequestError('')

    try {
      const createdUser = await createUser({
        nombre: values.nombre.trim(),
        correo: values.correo.trim(),
        password: values.password,
      })
      onCreated(createdUser)
      setValues(initialValues)
      setErrors({})
      dialogRef.current.close()
    } catch (error) {
      setValues((current) => ({ ...current, password: '' }))
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

  function closeDialog() {
    dialogRef.current.close()
  }

  return (
    <dialog
      aria-labelledby="create-user-title"
      aria-describedby="create-user-description"
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
            <h2 className="mt-2 text-2xl font-semibold tracking-tight" id="create-user-title">
              Nuevo usuario
            </h2>
          </div>
          <button
            aria-label="Cerrar formulario"
            className="grid size-9 shrink-0 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-[#10233f] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
            disabled={isSubmitting}
            onClick={closeDialog}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-600" id="create-user-description">
          Completa los datos de la persona que tendrá acceso a tu organización.
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
            <label className="block text-sm font-medium text-[#253a54]" htmlFor="create-user-name">
              Nombre
            </label>
            <input
              aria-describedby={errors.nombre ? 'create-user-name-error' : undefined}
              aria-invalid={Boolean(errors.nombre)}
              autoComplete="name"
              className={`${inputClasses} ${errors.nombre ? 'border-red-300' : 'border-[#cbd6e3]'}`}
              disabled={isSubmitting}
              id="create-user-name"
              maxLength={255}
              name="nombre"
              onChange={handleChange}
              placeholder="Nombre completo"
              ref={nameInputRef}
              required
              type="text"
              value={values.nombre}
            />
            {errors.nombre && <p className="mt-2 text-xs text-red-700" id="create-user-name-error">{errors.nombre}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-[#253a54]" htmlFor="create-user-email">
              Correo electrónico
            </label>
            <input
              aria-describedby={errors.correo ? 'create-user-email-error' : undefined}
              aria-invalid={Boolean(errors.correo)}
              autoComplete="email"
              className={`${inputClasses} ${errors.correo ? 'border-red-300' : 'border-[#cbd6e3]'}`}
              disabled={isSubmitting}
              id="create-user-email"
              maxLength={320}
              name="correo"
              onChange={handleChange}
              placeholder="nombre@empresa.com"
              ref={emailInputRef}
              required
              type="email"
              value={values.correo}
            />
            {errors.correo && <p className="mt-2 text-xs text-red-700" id="create-user-email-error">{errors.correo}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-[#253a54]" htmlFor="create-user-password">
              Contraseña inicial
            </label>
            <input
              aria-describedby={errors.password ? 'create-user-password-error' : undefined}
              aria-invalid={Boolean(errors.password)}
              autoComplete="new-password"
              className={`${inputClasses} ${errors.password ? 'border-red-300' : 'border-[#cbd6e3]'}`}
              disabled={isSubmitting}
              id="create-user-password"
              name="password"
              onChange={handleChange}
              placeholder="Escribe una contraseña"
              ref={passwordInputRef}
              required
              type="password"
              value={values.password}
            />
            {errors.password && <p className="mt-2 text-xs text-red-700" id="create-user-password-error">{errors.password}</p>}
          </div>

        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-[#e6edf5] px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p className="text-xs leading-5 text-slate-500 sm:max-w-44">La persona podrá iniciar sesión al crear su cuenta.</p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#cbd6e3] bg-white px-5 text-sm font-semibold text-[#10233f] transition hover:bg-[#f6f8fb] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
              disabled={isSubmitting}
              onClick={closeDialog}
              type="button"
            >
              Cancelar
            </button>
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#10233f] px-5 text-sm font-semibold text-white transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-65"
              disabled={isSubmitting}
              type="submit"
            >
              {isSubmitting ? 'Creando…' : 'Crear usuario'}
            </button>
          </div>
        </div>
      </form>
    </dialog>
  )
}

export default CreateUserForm
