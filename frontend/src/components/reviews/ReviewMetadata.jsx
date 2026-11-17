import { Star } from 'lucide-react'

const dateFormatter = new Intl.DateTimeFormat('es-MX', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const dateTimeFormatter = new Intl.DateTimeFormat('es-MX', {
  dateStyle: 'long',
  timeStyle: 'short',
})

export function ReviewDate({ value, withTime = false }) {
  if (!value) return 'Sin fecha'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Fecha no disponible'
  const formatter = withTime ? dateTimeFormatter : dateFormatter
  return <time dateTime={value}>{formatter.format(date)}</time>
}

export function ReviewRating({ value }) {
  if (value == null) return <span className="text-slate-600">Sin puntuación</span>

  return (
    <span className="inline-flex items-center gap-1 font-semibold text-slate-800">
      <Star aria-hidden="true" className="fill-amber-400 text-amber-400" size={16} />
      {`${value}/5`}
    </span>
  )
}

export function ReviewSource({ value }) {
  return value === 'manual' ? 'Manual' : value || 'Sin fuente'
}
