import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { analyticsService } from '../../services'
import AppLayout from '../../layouts/AppLayout'

const MONTH_NAMES = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export default function MonthlyReviewPage() {
  const { examId } = useParams()
  const queryClient = useQueryClient()

  const { data: reviews = [], isLoading } = useQuery({
    queryKey: ['monthly-reviews', examId],
    queryFn: () => analyticsService.listMonthlyReviews(examId),
  })

  const generateMutation = useMutation({
    mutationFn: () => analyticsService.generateMonthlyReview(examId),
    onSuccess: () => queryClient.invalidateQueries(['monthly-reviews', examId]),
  })

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto">
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <Link to={`/exams/${examId}/dashboard`} className="text-secondary/70 hover:text-secondary text-sm mb-1 transition-colors block">
              ← Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-secondary">Monthly Reviews</h1>
            <p className="text-secondary/70 text-sm mt-1">Generated on the 1st of each month</p>
          </div>
          <button
            id="generate-monthly-btn"
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="btn-primary text-sm"
          >
            {generateMutation.isPending ? '⏳ Generating…' : '✨ Generate This Month'}
          </button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : reviews.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-4xl mb-3">📆</p>
            <h3 className="text-secondary font-semibold mb-2">No monthly reviews yet</h3>
            <p className="text-secondary/70 text-sm mb-4">Reviews auto-generate on the 1st of each month, or generate one now.</p>
            <button onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending} className="btn-primary text-sm mx-auto">
              Generate now
            </button>
          </div>
        ) : (
          <div className="space-y-8">
            {reviews.map(r => (
              <div key={r.id} className="card space-y-4">
                <div className="flex items-start justify-between flex-wrap gap-2">
                  <div>
                    <h2 className="text-secondary font-bold text-xl">{MONTH_NAMES[r.month]} {r.year}</h2>
                    <p className="text-secondary/70 text-xs mt-0.5">{r.month_start_date} → {r.month_end_date}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-secondary/70 text-xs">Overall progress</p>
                    <p className="text-secondary font-bold text-lg">{r.exam_completion_pct?.toFixed(1)}%</p>
                  </div>
                </div>

                {/* Stats grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {[
                    { label: 'Planned Hours', value: `${r.planned_hours}h` },
                    { label: 'Actual Hours', value: `${r.actual_hours}h`, hi: r.actual_hours >= r.planned_hours },
                    { label: 'Topics Completed', value: r.topics_completed },
                    { label: 'Active Days', value: r.active_days },
                    { label: 'Days Missed', value: r.skipped_days },
                    { label: 'Productivity', value: r.avg_productivity_pct != null ? `${r.avg_productivity_pct}%` : '—' },
                  ].map(s => (
                    <div key={s.label} className="bg-tan/60 rounded-lg px-3 py-2">
                      <p className="text-secondary/70 text-xs">{s.label}</p>
                      <p className={`font-bold text-base ${s.hi ? 'text-emerald-400' : 'text-secondary'}`}>{s.value}</p>
                    </div>
                  ))}
                </div>

                {/* Prediction fields */}
                {(r.projected_finish_date || r.required_daily_hours) && (
                  <div className={`rounded-lg border p-3 text-sm ${r.on_track ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-amber-500/30 bg-amber-500/10'}`}>
                    <div className="flex flex-wrap gap-4">
                      {r.projected_finish_date && (
                        <div>
                          <p className="text-secondary/70 text-xs">Projected finish</p>
                          <p className="text-secondary font-semibold">{r.projected_finish_date}</p>
                        </div>
                      )}
                      {r.required_daily_hours && (
                        <div>
                          <p className="text-secondary/70 text-xs">Required daily hours</p>
                          <p className="text-secondary font-semibold">{r.required_daily_hours}h</p>
                        </div>
                      )}
                      {r.days_remaining_exam && (
                        <div>
                          <p className="text-secondary/70 text-xs">Days to exam</p>
                          <p className="text-secondary font-semibold">{r.days_remaining_exam}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Strong / Weak */}
                {(r.strong_topics?.length > 0 || r.weak_topics?.length > 0) && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {r.strong_topics?.length > 0 && (
                      <div>
                        <p className="text-emerald-400 text-xs font-semibold mb-2">💪 Strong This Month</p>
                        <div className="flex flex-wrap gap-2">
                          {r.strong_topics.map((t, i) => (
                            <span key={i} className="badge-low text-xs" title={t.reason}>{t.name}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {r.weak_topics?.length > 0 && (
                      <div>
                        <p className="text-amber-400 text-xs font-semibold mb-2">⚠ Focus Next Month</p>
                        <div className="flex flex-wrap gap-2">
                          {r.weak_topics.map((t, i) => (
                            <span key={i} className="badge-medium text-xs" title={t.reason}>{t.name}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="border-t border-secondary pt-4">
                  <p className="text-secondary text-sm leading-relaxed whitespace-pre-line">{r.ai_summary}</p>
                </div>

                {r.key_recommendation && (
                  <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-3">
                    <p className="text-indigo-300 text-xs font-semibold mb-1">🎯 Priority for Next Month</p>
                    <p className="text-secondary text-sm">{r.key_recommendation}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
