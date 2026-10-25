import AnalysisFeedback from './AnalysisFeedback.jsx'

function ReviewClassification({ canClassify, category, isClassifying, disabled, onClassify, error, succeeded }) {
  if (!canClassify) return null

  return (
    <section aria-label="Clasificación con IA" aria-busy={isClassifying} className="rounded-lg border border-slate-200 p-3">
      <h3 className="text-sm font-semibold text-slate-800">Clasificación</h3>
      <p className="mt-1 text-sm text-slate-700">{category || 'Sin clasificar'}</p>
      <button
        className="mt-2 w-full rounded-lg border border-sky-300 px-3 py-2 text-sm font-semibold text-sky-800 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={disabled || isClassifying}
        onClick={onClassify}
        type="button"
      >
        {isClassifying ? 'Clasificando…' : category ? 'Reclasificar con IA' : 'Clasificar con IA'}
      </button>
      <AnalysisFeedback loading={isClassifying} succeeded={succeeded} loadingText="Analizando la intención… Puede tardar unos segundos." successText="Categoría actualizada y guardada." />
      {error && <p className="mt-3 text-sm text-red-800" role="alert">{error}</p>}
    </section>
  )
}

export default ReviewClassification
