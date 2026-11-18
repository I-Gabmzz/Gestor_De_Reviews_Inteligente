import { LogOut } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import NotificationBell from './NotificationBell.jsx'
import { logout } from '../services/authService.js'
import { canAccessRoute } from '../utils/roleAccess.js'

const sections = [
  { path: '/dashboard', label: 'Resumen' },
  { path: '/reviews', label: 'Reseñas' },
  { path: '/imports', label: 'Importaciones' },
  { path: '/users', label: 'Usuarios' },
]

const roleLabels = {
  admin_general: 'Administrador general',
  admin_tenant: 'Administrador de negocio',
  usuario_negocio: 'Usuario de negocio',
}

export default function WorkspaceHeader({ user }) {
  const visibleSections = sections.filter(({ path }) => canAccessRoute(user.rol, path))

  function handleChangeAccount() {
    logout()
    window.location.replace('/')
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-8">
        <span className="text-lg font-semibold tracking-tight">GestorReviews</span>
        {visibleSections.length > 0 && (
          <nav aria-label="Navegación del negocio" className="flex min-w-0 flex-wrap gap-1 max-sm:w-full">
            {visibleSections.map(({ path, label }) => (
              <NavLink aria-current="location" className="workspace-nav-link" key={path} to={path}>
                {label}
              </NavLink>
            ))}
          </nav>
        )}
        <div aria-label="Sesión activa" className="flex w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-1 lg:ml-auto lg:w-auto" role="group">
          <NotificationBell user={user} />
          <button className="workspace-action" onClick={handleChangeAccount} title="Cerrar sesión y usar otra cuenta" type="button">
            <LogOut aria-hidden="true" size={15} />
            Cambiar cuenta
          </button>
          <p className="max-w-full text-xs text-slate-600 sm:max-w-48">
            <span className="block font-semibold">{roleLabels[user.rol]}</span>
            <span className="block wrap-anywhere">{user.correo || user.nombre}</span>
          </p>
        </div>
      </div>
    </header>
  )
}
