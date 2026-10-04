import { useState } from 'react'

import { REVIEW_STATUS_OPTIONS } from '../../utils/reviewStatus.js'

function ReviewStatusControl({ status, isSaving, onConfirm }) {
  const [selectedStatus, setSelectedStatus] = useState(status)
  const currentLabel = REVIEW_STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status

  function handleSubmit(event) {
    event.preventDefault()
    if (!isSaving && selectedStatus !== status) {
      onConfirm(selectedStatus)
    }
  }

  return (
    <form className="mt-6 border-t border-slate-100 pt-5" onSubmit={handleSubmit}>
      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="review-status">
        Estado de seguimiento
      </label>
      <p className="mt-1 text-sm text-slate-700" aria-live="polite">
        Estado actual: <span className="font-medium text-slate-900">{currentLabel}</span>
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <select
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 disabled:opacity-60"
          disabled={isSaving}
          id="review-status"
          onChange={(event) => setSelectedStatus(event.target.value)}
          value={selectedStatus}
        >
          {REVIEW_STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <button
          className="rounded-lg bg-sky-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isSaving || selectedStatus === status}
          type="submit"
        >
          {isSaving ? 'Guardando…' : 'Guardar estado'}
        </button>
      </div>
    </form>
  )
}

export default ReviewStatusControl
