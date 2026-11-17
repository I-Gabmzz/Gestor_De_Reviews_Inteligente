import { useState } from 'react'

import { REVIEW_STATUS_OPTIONS } from '../../utils/reviewStatus.js'

function ReviewStatusControl({ status, isSaving, onConfirm, feedback, disabled = false }) {
  const [draft, setDraft] = useState(null)
  const selectedStatus = draft ?? status
  const currentLabel = REVIEW_STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status

  async function handleSubmit(event) {
    event.preventDefault()
    if (disabled || isSaving || selectedStatus === status) {
      return
    }

    if (!REVIEW_STATUS_OPTIONS.some((option) => option.value === selectedStatus)) {
      setDraft(null)
      return
    }

    const confirmed = await onConfirm(selectedStatus)
    if (confirmed) {
      setDraft(null)
    }
  }

  return (
    <form className="mt-2" aria-busy={isSaving} onSubmit={handleSubmit}>
      <p className="text-sm text-slate-700" aria-live="polite">
        Estado actual: <span className="font-medium text-slate-900">{currentLabel}</span>
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1 basis-32">
          <label htmlFor="review-status">Nuevo estado</label>
          <select
            className="w-full min-w-0"
            disabled={disabled || isSaving}
            id="review-status"
            onChange={(event) => setDraft(event.target.value)}
            value={selectedStatus}
          >
            {REVIEW_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
        <button
          aria-disabled={isSaving || selectedStatus === status}
          className="workspace-action workspace-action-primary"
          disabled={disabled}
          type="submit"
        >
          {isSaving ? 'Guardando…' : 'Guardar estado'}
        </button>
      </div>
      {feedback?.kind === 'error' && (
        <p className="mt-2 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{feedback.message}</p>
      )}
      <p className="mt-2 text-sm text-emerald-800 empty:m-0" role="status">
        {feedback?.kind === 'success' && feedback.message}
      </p>
    </form>
  )
}

export default ReviewStatusControl
