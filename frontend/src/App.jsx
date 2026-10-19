import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'

import DashboardPage from './pages/DashboardPage.jsx'
import ImportReviewsPage from './pages/ImportReviewsPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ManualReviewPage from './pages/ManualReviewPage.jsx'
import ReviewsPage from './pages/ReviewsPage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import { getStoredSession } from './services/authService.js'
import { canAccessRoute, homeForRole } from './utils/roleAccess.js'

export function ProtectedRoute({ path, children }) {
  const session = getStoredSession()

  if (!session || homeForRole(session.user?.rol) === '/') return <Navigate replace to="/" />
  if (!canAccessRoute(session.user.rol, path)) return <Navigate replace to="/sin-acceso" />

  return children
}

function AccessDeniedPage() {
  const session = getStoredSession()
  if (!session) return <Navigate replace to="/" />
  const role = session.user?.rol

  return (
    <main className="grid min-h-screen place-items-center bg-[#eef2f7] px-5 text-[#10233f]">
      <section className="w-full max-w-lg rounded-2xl border border-[#d8e1ec] bg-white p-8 shadow-lg">
        <h1 className="text-2xl font-semibold">Acceso no permitido</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Tu rol no tiene permiso para abrir esta página. Si necesitas acceso, contacta a un administrador.
        </p>
        {homeForRole(role) !== '/' && (
          <Link className="mt-6 inline-block font-semibold text-[#0f766e] underline" to={homeForRole(role)}>
            Ir a mi inicio
          </Link>
        )}
      </section>
    </main>
  )
}

function AdminHomePage() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#eef2f7] px-5 text-[#10233f]">
      <section className="w-full max-w-xl rounded-2xl border border-[#d8e1ec] bg-white p-8 shadow-lg">
        <p className="text-sm font-medium text-[#0f766e]">Gestor Inteligente de Reviews</p>
        <h1 className="mt-2 text-3xl font-semibold">Administración general</h1>
        <p className="mt-4 text-sm leading-6 text-slate-600">
          Tu rol puede administrar tenants. Esta función todavía no tiene una pantalla en la aplicación.
        </p>
      </section>
    </main>
  )
}

function App() {
  return (
    <BrowserRouter>
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
