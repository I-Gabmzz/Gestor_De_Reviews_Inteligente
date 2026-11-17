import { useLayoutEffect, useRef, useState } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import DashboardPage from './pages/DashboardPage.jsx'
import ImportReviewsPage from './pages/ImportReviewsPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ManualReviewPage from './pages/ManualReviewPage.jsx'
import ReviewsPage from './pages/ReviewsPage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import AdminBusinessPanel from './components/AdminBusinessPanel.jsx'
import WorkspaceHeader from './components/WorkspaceHeader.jsx'
import { getStoredSession } from './services/authService.js'
import { SESSION_ENDED_EVENT } from './services/sessionStorage.js'
import { changeUserRole } from './services/userService.js'
import { canAccessRoute, homeForRole } from './utils/roleAccess.js'

export function ProtectedRoute({ path, children }) {
  const session = getStoredSession()

  if (!session || homeForRole(session.user?.rol) === '/') return <Navigate replace to="/" />
  if (!canAccessRoute(session.user.rol, path)) return <Navigate replace to="/sin-acceso" />

  return <><WorkspaceHeader user={session.user} />{children}</>
}

function AccessDeniedPage() {
  const session = getStoredSession()
  if (!session) return <Navigate replace to="/" />
  const role = session.user?.rol

  return (
    <main className="grid min-h-screen place-items-center bg-[#f5f5f7] px-5 text-[#1d1d1f]">
      <section className="w-full max-w-lg rounded-2xl border border-[#e5e5ea] bg-white p-8 shadow-lg">
        <h1 className="text-2xl font-semibold">Acceso no permitido</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Tu rol no tiene permiso para abrir esta página. Si necesitas acceso, contacta a un administrador.
        </p>
        {homeForRole(role) !== '/' && (
          <Link className="mt-6 inline-block font-semibold text-[#515154] underline" to={homeForRole(role)}>
            Ir a mi inicio
          </Link>
        )}
      </section>
    </main>
  )
}

function SessionRecovery() {
  const navigate = useNavigate()

  useLayoutEffect(() => {
    function onSessionEnded(event) {
      navigate('/', { replace: true, state: { sessionEnded: event.detail } })
    }

    window.addEventListener(SESSION_ENDED_EVENT, onSessionEnded)
    return () => window.removeEventListener(SESSION_ENDED_EVENT, onSessionEnded)
  }, [navigate])

  return null
}

function AdminHomePage() {
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState('admin_tenant')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [updated, setUpdated] = useState(null)
  const pending = useRef(false)

  async function handleRoleChange(event) {
    event.preventDefault()
    if (pending.current) return
    const id = Number(userId)
    if (!Number.isSafeInteger(id) || id <= 0) {
      setError('Ingresa un ID de usuario válido.')
      return
    }
    pending.current = true
    setSaving(true)
    setError('')
    setUpdated(null)
    try {
      setUpdated(await changeUserRole(id, role))
    } catch (caught) {
      const messages = {
        401: 'Tu sesión expiró. Inicia sesión nuevamente.',
        403: 'No tienes permiso para cambiar el rol de esta cuenta.',
        404: 'No se encontró la cuenta indicada.',
        422: 'El cambio solicitado no está permitido. Solo puedes promover un usuario o degradar un administrador de tenant.',
      }
      setError(messages[caught.response?.status] || 'No se pudo guardar el cambio de rol. Inténtalo nuevamente.')
    } finally {
      pending.current = false
      setSaving(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f5f7] px-5 py-8 text-[#1d1d1f]">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-medium text-[#515154]">Gestor Inteligente de Reviews</p>
        <h1 className="mt-2 text-3xl font-semibold">Administración general</h1>
        <AdminBusinessPanel />
        <section className="mt-8 rounded-2xl border border-[#e5e5ea] bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold">Cambiar rol de usuario</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Ingresa el ID de una cuenta de negocio y selecciona el nuevo rol.
          </p>
          <form className="mt-4 space-y-4" onSubmit={handleRoleChange} aria-busy={saving}>
            <label className="block text-sm font-medium" htmlFor="role-user-id">ID de usuario</label>
            <input className="w-full rounded-lg border border-slate-300 p-3" id="role-user-id" type="number" min="1" step="1" required disabled={saving} value={userId} onChange={(event) => { setUserId(event.target.value); setUpdated(null); setError('') }} />
            <label className="block text-sm font-medium" htmlFor="user-new-role">Nuevo rol</label>
            <select className="w-full rounded-lg border border-slate-300 p-3" id="user-new-role" disabled={saving} value={role} onChange={(event) => { setRole(event.target.value); setUpdated(null); setError('') }}>
              <option value="admin_tenant">Administrador de tenant</option>
              <option value="usuario_negocio">Usuario de negocio</option>
            </select>
            <button className="w-full rounded-lg bg-[#515154] px-4 py-3 font-semibold text-white disabled:opacity-60" type="submit" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar rol'}
            </button>
            {error && <p className="text-sm text-red-800" role="alert">{error}</p>}
            {updated && <p className="text-sm text-emerald-800" role="status">Rol guardado para {updated.nombre} (ID {updated.id}): {updated.rol === 'admin_tenant' ? 'Administrador de tenant' : 'Usuario de negocio'}.</p>}
          </form>
        </section>
      </div>
    </main>
  )
}

function App() {
  return (
    <BrowserRouter>
      <SessionRecovery />
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/dashboard" element={<ProtectedRoute path="/dashboard"><DashboardPage /></ProtectedRoute>} />
        <Route path="/imports" element={<ProtectedRoute path="/imports"><ImportReviewsPage /></ProtectedRoute>} />
        <Route path="/reviews" element={<ProtectedRoute path="/reviews"><ReviewsPage /></ProtectedRoute>} />
        <Route path="/reviews/new" element={<ProtectedRoute path="/reviews/new"><ManualReviewPage /></ProtectedRoute>} />
        <Route path="/users" element={<ProtectedRoute path="/users"><UsersPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute path="/admin"><AdminHomePage /></ProtectedRoute>} />
        <Route path="/sin-acceso" element={<AccessDeniedPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
