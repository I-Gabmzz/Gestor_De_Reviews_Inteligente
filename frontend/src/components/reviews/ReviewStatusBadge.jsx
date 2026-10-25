import { REVIEW_STATUS_OPTIONS } from '../../utils/reviewStatus.js'

const styles = {
  nueva: 'border-slate-300 bg-slate-50 text-slate-600',
  en_revision: 'border-amber-200 bg-amber-50 text-amber-800',
  atendida: 'border-emerald-200 bg-emerald-50 text-emerald-800',
}

function ReviewStatusBadge({ status }) {
  const normalized = String(status || '').toLowerCase()
  const label = REVIEW_STATUS_OPTIONS.find((option) => option.value === normalized)?.label || normalized.replaceAll('_', ' ') || 'Sin estado'

  return (
    <span className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium ${styles[normalized] || styles.nueva}`}>
      {label}
    </span>
  )
}

export default ReviewStatusBadge
