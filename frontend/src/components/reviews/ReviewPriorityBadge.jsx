import { TriangleAlert } from 'lucide-react'

function ReviewPriorityBadge({ priority }) {
  const high = priority === 'Alta'
  return (
    <span
      aria-label={priority ? `Prioridad: ${priority}` : 'Prioridad sin determinar'}
      className={`inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-semibold ${high ? 'border-[#f0b9b4] bg-[#fff4f2] text-[#9f241b]' : 'border-slate-200 bg-slate-50 text-slate-600'}`}
    >
      {high && <TriangleAlert aria-hidden="true" size={13} className="shrink-0" />}
      {priority || 'Sin determinar'}
    </span>
  )
}

export default ReviewPriorityBadge
