function ReviewClassification({ canClassify, category, isClassifying, disabled, onClassify, error, succeeded }) {
  if (!canClassify) return null

  return (
    <section aria-label="Clasificación con IA" className="mt-5 rounded-lg border border-slate-200 p-4">
      <button
        className="w-full rounded-lg border border-sky-300 px-3 py-2.5 text-sm font-semibold text-sky-800 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={disabled || isClassifying}
        onClick={onClassify}
        type="button"
      >
        {isClassifying ? 'Clasificando…' : category ? 'Clasificar nuevamente con IA' : 'Clasificar con IA'}
      </button>
      {isClassifying && <p className="mt-2 text-sm text-slate-600" role="status">Analizando la intención de esta review…</p>}
      {succeeded && <p className="mt-2 text-sm text-emerald-800" role="status">Categoría actualizada.</p>}
      {error && <p className="mt-3 text-sm text-red-800" role="alert">{error}</p>}
    </section>
  )
}

export default ReviewClassification
