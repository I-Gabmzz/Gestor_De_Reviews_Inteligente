import { CheckCircle2, LoaderCircle } from 'lucide-react'

function AnalysisFeedback({ loading, succeeded, loadingText, successText }) {
  if (!loading && !succeeded) return null

  return (
    <div role="status" aria-live="polite" className={`mt-2 flex items-start gap-2 rounded-lg px-2.5 py-2 text-xs ${loading ? 'bg-sky-50 text-sky-800' : 'bg-emerald-50 text-emerald-800'}`}>
      {loading ? <LoaderCircle aria-hidden="true" className="mt-0.5 shrink-0 motion-safe:animate-spin" size={15} /> : <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={15} />}
      <span>{loading ? loadingText : successText}</span>
    </div>
  )
}

export default AnalysisFeedback
