const PACE_CONFIG = {
  ahead:    { color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', label: '↑ Ahead of Plan' },
  on_track: { color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',   label: '✓ On Track' },
  behind:   { color: 'bg-amber-500/20 text-amber-400 border-amber-500/30',       label: '↓ Behind Plan' },
  at_risk:  { color: 'bg-red-500/20 text-red-400 border-red-500/30',             label: '⚠ At Risk' },
}

const RISK_DOT = {
  low:    'bg-emerald-500',
  medium: 'bg-amber-500',
  high:   'bg-red-500',
}

const CONFIDENCE_LABELS = {
  1: 'Confused', 2: 'Struggled', 3: 'Okay', 4: 'Understood', 5: 'Nailed it!'
}

export default function FeedbackCard({ feedback, planAdjusted, adjustmentSummary, showDate = false }) {
  if (!feedback) return null

  const pace = PACE_CONFIG[feedback.pace_status] || PACE_CONFIG.on_track

  return (
    <div className="card space-y-4">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${pace.color}`}>
            {pace.label}
          </span>
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${RISK_DOT[feedback.risk_level] || 'bg-slate-500'}`} />
            <span className="text-slate-500 text-xs capitalize">{feedback.risk_level} risk</span>
          </span>
          {feedback.confidence_display && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700/60 text-slate-400">
              Confidence {feedback.confidence_display}/5 — {CONFIDENCE_LABELS[feedback.confidence_display] || ''}
            </span>
          )}
        </div>
        {showDate && feedback.plan_date && (
          <span className="text-slate-500 text-xs">
            {new Date(feedback.plan_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
          </span>
        )}
      </div>

      {/* Performance summary */}
      <p className="text-white text-sm leading-relaxed">{feedback.performance_summary}</p>

      {/* Suggestions */}
      {feedback.suggestions?.length > 0 && (
        <div>
          <p className="text-slate-500 text-xs uppercase tracking-wider font-medium mb-2">Suggestions</p>
          <ul className="space-y-1.5">
            {feedback.suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-indigo-400 text-xs mt-0.5 shrink-0">→</span>
                <span className="text-slate-300 text-sm">{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Motivational note */}
      {feedback.motivational_note && (
        <p className="text-slate-400 text-sm italic border-t border-slate-700 pt-3">
          "{feedback.motivational_note}"
        </p>
      )}

      {/* Plan adjustment banner */}
      {planAdjusted && adjustmentSummary && (
        <div className="flex items-start gap-2 p-3 rounded-lg border border-indigo-500/30 bg-indigo-500/10">
          <span className="text-indigo-400 shrink-0">📋</span>
          <div>
            <p className="text-indigo-300 text-xs font-semibold">Plan Updated</p>
            <p className="text-indigo-400 text-xs mt-0.5">{adjustmentSummary}</p>
          </div>
        </div>
      )}
    </div>
  )
}
