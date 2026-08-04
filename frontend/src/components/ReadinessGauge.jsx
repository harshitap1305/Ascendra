/**
 * ReadinessGauge — SVG arc gauge showing 0-100 readiness score.
 * Also shows the weight breakdown below (40/25/20/15).
 * Colors: red < 40, amber 40-69, indigo 70-89, emerald ≥ 90
 */

const RADIUS = 54
const CIRCUMFERENCE = Math.PI * RADIUS   // half circle = π * r

function arcColor(score) {
  if (score >= 90) return '#10b981'  // emerald
  if (score >= 70) return '#6366f1'  // indigo
  if (score >= 40) return '#f59e0b'  // amber
  return '#ef4444'                   // red
}

function arcLabel(score) {
  if (score >= 90) return 'Exam Ready'
  if (score >= 70) return 'On Track'
  if (score >= 40) return 'Moderate'
  return 'Needs Attention'
}

export default function ReadinessGauge({ score = 0, breakdown = {} }) {
  // The arc is a half-circle (180°) — strokeDashoffset controls fill
  const filled = (score / 100) * CIRCUMFERENCE
  const empty = CIRCUMFERENCE - filled
  const color = arcColor(score)

  const weights = breakdown.weights || { completion: '40%', consistency: '25%', pace: '20%', confidence: '15%' }
  const components = [
    { key: 'completion',  label: 'Syllabus Done',  weight: weights.completion,  val: breakdown.completion  ?? 0, color: '#818cf8' },
    { key: 'consistency', label: 'Consistency',    weight: weights.consistency, val: breakdown.consistency ?? 0, color: '#34d399' },
    { key: 'pace',        label: 'Pace',           weight: weights.pace,        val: breakdown.pace        ?? 0, color: '#fb923c' },
    { key: 'confidence',  label: 'Confidence',     weight: weights.confidence,  val: breakdown.confidence  ?? 0, color: '#a78bfa' },
  ]

  return (
    <div className="card flex flex-col items-center gap-4">
      {/* Arc SVG */}
      <div className="relative">
        <svg width={160} height={90} viewBox="0 0 160 90">
          {/* Background track */}
          <path
            d="M 10 80 A 70 70 0 0 1 150 80"
            fill="none"
            stroke="#1e293b"
            strokeWidth={14}
            strokeLinecap="round"
          />
          {/* Foreground arc */}
          <path
            d="M 10 80 A 70 70 0 0 1 150 80"
            fill="none"
            stroke={color}
            strokeWidth={14}
            strokeLinecap="round"
            strokeDasharray={`${(score / 100) * 220} 220`}
            style={{ transition: 'stroke-dasharray 1s ease-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span className="text-3xl font-bold text-white">{score}</span>
          <span className="text-xs font-semibold" style={{ color }}>{arcLabel(score)}</span>
        </div>
      </div>

      {/* Weight breakdown — shown to user */}
      <div className="w-full border-t border-slate-800 pt-3">
        <p className="text-slate-500 text-xs text-center mb-2">Score breakdown</p>
        <div className="grid grid-cols-2 gap-1.5">
          {components.map(c => (
            <div key={c.key} className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: c.color }} />
              <div className="min-w-0">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400 truncate">{c.label}</span>
                  <span className="text-slate-300 font-medium ml-1">{c.weight}</span>
                </div>
                <div className="h-1 bg-slate-800 rounded-full mt-0.5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${c.val}%`, background: c.color }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
