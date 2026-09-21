import { Link } from 'react-router-dom'


function DashboardPlaceholder() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#eef2f7] px-6 text-center text-[#10233f]">
      <div>
        <p className="text-sm font-medium text-[#0f766e]">Sesión iniciada</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em]">Tu dashboard estará aquí</h1>
        <p className="mt-3 text-sm text-slate-500">La vista del negocio se implementará en una futura Historia de Usuario.</p>
        <Link
          className="mt-6 inline-flex rounded-xl bg-[#10233f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#19365c] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200"
          to="/reviews"
        >
          Consultar reviews
        </Link>
      </div>
    </main>
  )
}

export default DashboardPlaceholder
