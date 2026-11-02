import { useEffect, useId, useRef, useState } from 'react'
import { Bell, ChevronLeft, ChevronRight, RefreshCw, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import useNotifications from '../hooks/useNotifications.js'
import { NOTIFICATION_PAGE_SIZE } from '../services/notificationService.js'
import { canAccessRoute } from '../utils/roleAccess.js'

const dateFormatter = new Intl.DateTimeFormat('es-MX', { dateStyle: 'short', timeStyle: 'short' })

export default function NotificationBell({ user }) {
  const enabled = user?.tenant_id != null && canAccessRoute(user?.rol, '/reviews')
  const notifications = useNotifications(user, enabled)
  const [open, setOpen] = useState(false)
  const container = useRef(null)
  const trigger = useRef(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return undefined
    function outside(event) {
      if (!container.current?.contains(event.target)) setOpen(false)
    }
    function escape(event) {
      if (event.key === 'Escape') {
        setOpen(false)
        trigger.current?.focus()
      }
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  if (!enabled) return null
  const pageStart = notifications.offset || 0

  return (
    <div ref={container} className="relative">
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Avisos de prioridad alta${notifications.total ? `: ${notifications.total}` : ''}`}
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600"
        onClick={() => { if (!open) notifications.load(0); setOpen((value) => !value) }}
      >
        <Bell aria-hidden="true" size={15} />
        Avisos
        {notifications.total > 0 && <span className="rounded-full bg-slate-900 px-1.5 py-0.5 text-[10px] text-white">{notifications.total}</span>}
      </button>
      {open && (
        <section id={panelId} aria-label="Avisos de prioridad alta" aria-busy={notifications.loading} className="absolute left-0 z-50 mt-2 w-[min(22rem,calc(100vw-2.5rem))] overflow-hidden rounded-2xl border border-slate-200 bg-white text-slate-900 shadow-lg lg:right-0 lg:left-auto">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold">Prioridad alta</h2>
              <p className="mt-0.5 text-xs font-normal text-slate-500">{notifications.total} {notifications.total === 1 ? 'review con aviso vigente' : 'reviews con aviso vigente'}</p>
            </div>
            <button type="button" aria-label="Cerrar avisos" onClick={() => { setOpen(false); trigger.current?.focus() }} className="rounded-full p-1.5 text-slate-500 hover:bg-slate-100"><X aria-hidden="true" size={16} /></button>
          </div>
          {notifications.loading && <p role="status" className="px-4 py-3 text-xs text-slate-500">Actualizando avisos…</p>}
          {notifications.error && (
            <div className="px-4 py-3">
              <p role="alert" className="text-xs font-normal text-red-800">{notifications.error}</p>
              <button type="button" disabled={notifications.loading} onClick={() => notifications.load(0)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-slate-800 disabled:opacity-50"><RefreshCw aria-hidden="true" size={13} />Reintentar avisos</button>
            </div>
          )}
          {!notifications.loading && !notifications.error && notifications.items.length === 0 && <p className="px-4 py-6 text-sm font-normal text-slate-500">No hay avisos de prioridad alta.</p>}
          <ul className="max-h-[50vh] divide-y divide-slate-100 overflow-y-auto">
            {notifications.items.map((item) => (
              <li key={item.id}>
                <Link to={`/reviews?review=${item.review_id}`} onClick={() => setOpen(false)} className="block px-4 py-3 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-sky-600">
                  <span className="flex items-center justify-between gap-2 text-xs font-semibold"><span>{item.autor || 'Cliente anónimo'}</span><span className="shrink-0 text-[#9f241b]">Alta</span></span>
                  <p className="mt-1 line-clamp-2 break-words text-xs font-normal leading-5 text-slate-600">{item.extracto}</p>
                  <time dateTime={item.creada_en} className="mt-1 block text-[11px] font-normal text-slate-500">{dateFormatter.format(new Date(item.creada_en))}</time>
                </Link>
              </li>
            ))}
          </ul>
          {notifications.total > NOTIFICATION_PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2 text-xs">
              <button type="button" aria-label="Avisos anteriores" disabled={notifications.loading || pageStart === 0} onClick={() => notifications.load(Math.max(0, pageStart - NOTIFICATION_PAGE_SIZE))} className="inline-flex items-center gap-1 rounded-full px-2 py-1.5 disabled:opacity-40"><ChevronLeft aria-hidden="true" size={13} />Anterior</button>
              <span>{pageStart + 1}–{Math.min(pageStart + NOTIFICATION_PAGE_SIZE, notifications.total)}</span>
              <button type="button" aria-label="Avisos siguientes" disabled={notifications.loading || pageStart + NOTIFICATION_PAGE_SIZE >= notifications.total} onClick={() => notifications.load(pageStart + NOTIFICATION_PAGE_SIZE)} className="inline-flex items-center gap-1 rounded-full px-2 py-1.5 disabled:opacity-40">Siguiente<ChevronRight aria-hidden="true" size={13} /></button>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
