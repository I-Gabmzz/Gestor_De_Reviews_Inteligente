import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { login } from '../services/authService.js'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function LoginPage() {
  const navigate = useNavigate()
  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()

    if (loading) {
      return
    }

    const nextErrors = {}
    const normalizedCorreo = correo.trim()

    if (!normalizedCorreo) {
      nextErrors.correo = 'Ingresa tu correo para continuar.'
    } else if (!emailPattern.test(normalizedCorreo)) {
      nextErrors.correo = 'Revisa el formato de tu correo.'
    }

    if (!password) {
      nextErrors.password = 'Ingresa tu contraseña para continuar.'
    }

    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setLoading(true)

    try {
      await login({ correo: normalizedCorreo, password })
      navigate('/dashboard')
    } catch (error) {
      setErrors({ general: error.message })
    } finally {
      setLoading(false)
    }
  }

  function handleCorreoChange(event) {
    setCorreo(event.target.value)
    setErrors((currentErrors) => ({ ...currentErrors, correo: undefined, general: undefined }))
  }

  function handlePasswordChange(event) {
    setPassword(event.target.value)
    setErrors((currentErrors) => ({ ...currentErrors, password: undefined, general: undefined }))
  }

  return (
    <main className="min-h-screen bg-[#eef2f7] text-[#10233f] lg:grid lg:grid-cols-[minmax(20rem,0.82fr)_minmax(34rem,1.18fr)]">
      <section className="relative hidden min-h-screen overflow-hidden bg-[#10233f] px-10 py-10 text-white lg:flex lg:flex-col lg:justify-between xl:px-16">
        <div aria-hidden="true" className="absolute -right-28 top-24 size-72 rounded-full border border-white/10" />
        <div aria-hidden="true" className="absolute -right-12 top-40 size-40 rounded-full border border-teal-300/20" />

        <div className="relative z-10 flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-teal-300 font-bold text-[#10233f] shadow-[0_10px_30px_rgba(94,234,212,0.18)]">
            GI
          </span>
          <span className="text-sm font-semibold tracking-[-0.01em]">Gestor Inteligente de Reviews</span>
        </div>

        <div className="relative z-10 max-w-md pb-8">
          <p className="mb-5 text-sm font-medium text-teal-200">Tu operación, con mejor contexto</p>
          <h1 className="max-w-lg text-4xl font-semibold leading-[1.08] tracking-[-0.045em] text-balance xl:text-5xl">
            Convierte cada reseña en una señal para tu negocio.
          </h1>
          <p className="mt-6 max-w-sm text-base leading-7 text-slate-300">
            Centraliza la voz de tus clientes y encuentra lo importante sin perder el pulso del día a día.
          </p>

          <div className="mt-12 flex items-end gap-3" aria-hidden="true">
            <div className="h-10 w-2 rounded-full bg-teal-300/45" />
            <div className="h-16 w-2 rounded-full bg-teal-300/65" />
            <div className="h-24 w-2 rounded-full bg-teal-300" />
            <div className="ml-2 h-px w-20 bg-white/25" />
            <span className="pb-1 text-xs text-slate-400">señal de clientes</span>
          </div>
        </div>

        <p className="relative z-10 text-xs text-slate-400">Un espacio claro para decisiones más cercanas.</p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-5 py-8 sm:px-8 lg:px-12 xl:px-20">
        <div className="w-full max-w-[31rem]">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid size-10 place-items-center rounded-xl bg-[#10233f] text-sm font-bold text-teal-200">
              GI
            </span>
            <span className="text-sm font-semibold tracking-[-0.01em]">Gestor Inteligente de Reviews</span>
          </div>

          <div className="rounded-[1.5rem] border border-[#d8e1ec] bg-white p-6 shadow-[0_24px_70px_rgba(16,35,63,0.10)] sm:p-9">
            <div className="mb-8">
              <p className="mb-3 text-sm font-medium text-[#0f766e]">Bienvenido de nuevo</p>
              <h2 className="text-3xl font-semibold tracking-[-0.045em] text-[#10233f]">Inicia sesión</h2>
              <p className="mt-3 max-w-sm text-sm leading-6 text-slate-500">
                Accede a tu espacio de negocio y mantén tus reseñas bajo control.
              </p>
            </div>

            <form className="space-y-5" noValidate onSubmit={handleSubmit}>
              {errors.general && (
                <p
                  aria-live="polite"
                  className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-5 text-red-700"
                  role="alert"
                >
                  {errors.general}
                </p>
              )}

              <div>
                <label className="mb-2 block text-sm font-medium text-[#253a54]" htmlFor="correo">
                  Correo electrónico
                </label>
                <input
                  aria-describedby={errors.correo ? 'correo-error' : undefined}
                  aria-invalid={Boolean(errors.correo)}
                  autoComplete="email"
                  className="w-full rounded-xl border border-[#cbd6e3] bg-[#fbfcfe] px-4 py-3 text-base text-[#10233f] outline-none transition placeholder:text-slate-400 focus:border-[#0f766e] focus:ring-4 focus:ring-teal-100"
                  id="correo"
                  name="correo"
                  onChange={handleCorreoChange}
                  placeholder="nombre@empresa.com"
                  required
                  type="email"
                  value={correo}
                />
                {errors.correo && (
                  <p className="mt-2 text-sm text-red-700" id="correo-error" role="alert">
                    {errors.correo}
                  </p>
                )}
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-[#253a54]" htmlFor="password">
                  Contraseña
                </label>
                <input
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  aria-invalid={Boolean(errors.password)}
                  autoComplete="current-password"
                  className="w-full rounded-xl border border-[#cbd6e3] bg-[#fbfcfe] px-4 py-3 text-base text-[#10233f] outline-none transition placeholder:text-slate-400 focus:border-[#0f766e] focus:ring-4 focus:ring-teal-100"
                  id="password"
                  name="password"
                  onChange={handlePasswordChange}
                  placeholder="Escribe tu contraseña"
                  required
                  type="password"
                  value={password}
                />
                {errors.password && (
                  <p className="mt-2 text-sm text-red-700" id="password-error" role="alert">
                    {errors.password}
                  </p>
                )}
              </div>

              <div className="flex justify-end pt-1">
                <button
                  className="text-sm font-medium text-[#0f766e] underline decoration-transparent underline-offset-4 transition hover:decoration-current focus-visible:rounded focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
                  type="button"
                >
                  ¿Olvidaste tu contraseña?
                </button>
              </div>

              <button
                aria-disabled={loading}
                className="w-full rounded-xl bg-[#10233f] px-4 py-3.5 text-sm font-semibold text-white shadow-[0_12px_22px_rgba(16,35,63,0.18)] transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-70"
                disabled={loading}
                type="submit"
              >
                {loading ? 'Validando acceso…' : 'Iniciar sesión'}
              </button>
            </form>
          </div>

          <p className="mt-6 text-center text-xs leading-5 text-slate-500">
            Gestiona la conversación con tus clientes desde un solo lugar.
          </p>
        </div>
      </section>
    </main>
  )
}

export default LoginPage
