import { useEffect, useState } from 'react'
import { AlertCircle, ArrowLeft, Plus, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'

import { getUsers } from '../services/userService.js'

const columns = ['Nombre', 'Correo', 'Rol', 'Estado', 'Acciones']
const roleLabels = {
  usuario_negocio: 'Usuario',
  admin_tenant: 'Administrador',
}
const stateLabels = {
  activo: 'Activo',
  inactivo: 'Inactivo',
}

function getErrorMessage(error) {
  if (error.response?.status === 401) {
    return 'Tu sesión no es válida. Inicia sesión nuevamente.'
  }
  if (error.response?.status === 403) {
    return 'Tu usuario no tiene permiso para gestionar usuarios de esta organización.'
  }
  return 'No fue posible cargar los usuarios. Intenta nuevamente más tarde.'
}

function UsersPage() {
  const [users, setUsers] = useState([])
  const [status, setStatus] = useState('loading')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    async function loadUsers() {
      try {
        const data = await getUsers({ signal: controller.signal })
        if (!controller.signal.aborted) {
          setUsers(data.items)
          setStatus('ready')
        }
      } catch (error) {
        if (!controller.signal.aborted && error.code !== 'ERR_CANCELED') {
          setErrorMessage(getErrorMessage(error))
          setStatus('error')
        }
      }
    }

    loadUsers()
    return () => controller.abort()
  }, [])

  return (
    <main className="min-h-screen bg-[#eef2f7] px-5 py-6 text-[#10233f] sm:px-8 sm:py-8 lg:px-10">
      <div className="mx-auto w-full max-w-6xl">
        <Link
          className="inline-flex items-center gap-2 rounded-md text-sm font-medium text-[#0f766e] transition hover:text-[#0b5f59] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100"
          to="/dashboard"
        >
          <ArrowLeft aria-hidden="true" size={16} />
          Volver al dashboard
        </Link>

        <header className="mt-7 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-[#0f766e]">Equipo y acceso</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#10233f] sm:text-4xl">
              Gestión de usuarios
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
              Administra las personas que tienen acceso a tu organización.
            </p>
          </div>
          <div className="shrink-0">
            <button
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#10233f] px-5 py-2.5 text-sm font-semibold text-white opacity-55 sm:w-auto"
              disabled
              type="button"
            >
              <Plus aria-hidden="true" size={17} />
              Nuevo usuario
            </button>
            <p className="mt-2 text-center text-xs text-slate-500 sm:text-right">
              Disponible próximamente
            </p>
          </div>
        </header>

        <section
          aria-labelledby="users-list-title"
          className="mt-8 overflow-hidden rounded-2xl border border-[#d8e1ec] bg-white shadow-[0_10px_30px_rgba(16,35,63,0.04)]"
        >
          <div className="flex items-center justify-between border-b border-[#e6edf5] px-6 py-5 sm:px-8">
            <h2 className="text-base font-semibold text-[#10233f]" id="users-list-title">
              Usuarios
            </h2>
            <span className="text-xs text-slate-500">Listado de la organización</span>
          </div>

          {status === 'loading' && (
            <div aria-live="polite" className="px-6 py-16 text-center text-sm text-slate-500" role="status">
              Cargando usuarios…
            </div>
          )}

          {status === 'error' && (
            <div className="flex items-start gap-3 px-6 py-8 text-sm text-red-800 sm:px-8" role="alert">
              <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
              <p>{errorMessage}</p>
            </div>
          )}

          {status === 'ready' && (
            <>
              <div className={`${users.length === 0 ? 'hidden sm:block' : 'block'} overflow-x-auto px-6 sm:px-8`}>
                <table className="w-full min-w-[42rem] table-fixed border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-[#e6edf5] text-xs font-medium text-slate-500">
                      {columns.map((column) => (
                        <th className="px-2 py-4 font-medium first:pl-0 last:pr-0" key={column} scope="col">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e6edf5]">
                    {users.map((user) => (
                      <tr key={user.id}>
                        <td className="break-words py-5 pr-2 font-medium text-[#10233f]">{user.nombre}</td>
                        <td className="break-all px-2 py-5 text-slate-600">{user.correo}</td>
                        <td className="px-2 py-5 text-slate-600">{roleLabels[user.rol] ?? user.rol}</td>
                        <td className="px-2 py-5">
                          <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${user.estado === 'activo' ? 'border-teal-200 bg-teal-50 text-teal-800' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
                            {stateLabels[user.estado] ?? user.estado}
                          </span>
                        </td>
                        <td className="py-5 pl-2 text-center text-slate-400">
                          <span aria-label="Sin acciones disponibles">—</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {users.length === 0 && (
                <div className="flex flex-col items-center px-6 py-16 text-center sm:px-8 sm:py-20">
                  <span className="grid size-14 place-items-center rounded-2xl bg-[#f1f5f9] text-[#64748b]">
                    <UsersRound aria-hidden="true" size={25} strokeWidth={1.7} />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold tracking-tight text-[#10233f]">
                    Todavía no hay usuarios para mostrar
                  </h3>
                  <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
                    Los usuarios de tu organización aparecerán aquí cuando se agreguen.
                  </p>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  )
}

export default UsersPage
